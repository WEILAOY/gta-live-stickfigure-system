"""YOLOX-Nano ONNX inference and a single-slot background work queue.

Model: Megvii-BaseDetection/YOLOX, official 0.1.1rc0 release.
Pre/postprocessing follows the documented YOLOX model contract: top-left BGR
letterbox at 0..255, raw grid/stride outputs and objectness * class probability.
The box detector does not infer game state. The optional scene analyzer adds
pose landmarks and conservative scene estimates in the same background worker.
"""
from dataclasses import dataclass,replace
from pathlib import Path
import queue
import threading
import time
from .core import Joint,Horizon

MODEL_PROFILES={"快速":"yolox_nano.onnx","均衡":"yolox_tiny.onnx","精细":"yolox_s.onnx"}
MAX_PEOPLE=8
MAX_VEHICLES=4
MAX_DOGS=3

def unrotate_box(box,turns):
    a,b,c,d=box
    return (1-d,a,1-b,c) if turns==1 else (b,1-c,d,1-a) if turns==3 else box

def merge_down_proposals(normal,proposals,width,height):
    """Require a rotated person detection and horizontal extent, not width alone."""
    from .tracking import overlap
    result=list(normal)
    for proposal,turns in sorted(proposals,key=lambda p:p[0].confidence,reverse=True):
        box=unrotate_box(proposal.box,turns);a,b,c,d=box
        aspect=(c-a)*width/max(1,(d-b)*height);area=(c-a)*(d-b)
        if aspect<1.4 or (c-a)*width<38 or (d-b)*height<12 or area>.45:continue
        supports=[n for n in normal if n.label=='person' and overlap(n.box,box)>.40 and
                  (n.box[2]-n.box[0])*width/max(1,(n.box[3]-n.box[1])*height)>.85]
        if proposal.confidence<.45 or (not supports and (proposal.confidence<.65 or aspect<1.6 or area>.22)):continue
        # Current-frame cross-view agreement can confirm a paused first frame.
        # A lone weaker candidate still needs normal temporal confirmation.
        if supports:
            # Preserve normal-view box, confidence and prop context. A false
            # rotated portrait proposal must not move or reclassify its actor.
            supported=max(supports,key=lambda n:overlap(n.box,box))
            candidate=replace(supported,posture_hint='DOWN',action_mirror=turns==3,corroborated=True)
        else:
            candidate=replace(proposal,box=box,render_box=unrotate_box(proposal.render_box or proposal.box,turns),
                              posture_hint='DOWN',action_mirror=turns==3,object_hints=())
        if any(n.label=='person' and n.posture_hint=='DOWN' and overlap(n.box,box)>.4 for n in result):continue
        result=[n for n in result if not (n.label=='person' and overlap(n.box,box)>.40)]
        result.append(candidate)
    people=sorted((n for n in result if n.label=='person'),key=lambda n:n.confidence,reverse=True)[:MAX_PEOPLE]
    vehicles=[n for n in result if n.label not in ('person','dog')][:MAX_VEHICLES]
    dogs=[n for n in result if n.label=='dog'][:MAX_DOGS]
    return tuple(people+vehicles+dogs)


def person_fragment(det,other):
    """Reject only weak, nested, top-aligned duplicates of a stronger person."""
    if det.label!='person' or other.label!='person' or det.confidence>=.60 or other.confidence<.60:
        return False
    a,b=det.box,other.box
    aw,ah=a[2]-a[0],a[3]-a[1];bw,bh=b[2]-b[0],b[3]-b[1]
    area=aw*ah
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return (area>0 and area<bw*bh*.5 and intersection/area>.90
            and abs(a[1]-b[1])<bh*.05 and abs((a[0]+a[2]-b[0]-b[2])/2)<bw*.12)


@dataclass(frozen=True)
class ObjectHint:
    label: str
    confidence: float
    box: tuple[float,float,float,float]


def attach_object_hints(detections,hints):
    """Context only: props never enter the drawable people/vehicle list."""
    output=[]
    for det in detections:
        context=[]
        if det.label=='person':
            a,b,c,d=det.box;w,h=c-a,d-b
            for hint in hints:
                x,y=(hint.box[0]+hint.box[2])/2,(hint.box[1]+hint.box[3])/2
                if hint.label in ('chair','couch'):
                    if hint.confidence>.55 and a-w*.15<=x<=c+w*.15 and b+h*.45<=y<=d+h*.10:
                        context.append(hint)
                    continue
                if hint.confidence>=.40 and a-w*.12<=x<=c+w*.12 and b-h*.05<=y<=b+h*.80:
                    context.append(hint)
        output.append(replace(det,object_hints=tuple(context[:3])))
    return tuple(output)


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[float,float,float,float]
    track_id: str = ""
    pose: tuple[Joint,...] = ()
    action: str = "UNKNOWN"
    yaw: float = 0.0
    view_confidence: float = 0.0
    predicted: bool = False
    missing_age: float = 0.0
    velocity: tuple[float,float] = (0.0,0.0)
    render_box: tuple[float,float,float,float] | None = None
    confirmed: bool = True
    object_hints: tuple[ObjectHint,...] = ()
    action_mirror: bool = False
    posture_hint: str = ''
    corroborated: bool = False
    weapon_boxes: tuple = ()
    weapon_scores: tuple = ()
    seated: bool = False
    seat_mirror: bool = False


@dataclass(frozen=True)
class DetectionResult:
    epoch: int
    generation: int
    timestamp: float
    detections: tuple[Detection,...]
    inference_ms: float
    total_ms: float
    backend: str
    horizon: Horizon | None = None
    scene_revision: int = 0


class YoloXDetector:
    def __init__(self,model_path,context_enabled=True):
        import cv2
        import numpy as np
        self.cv2,self.np = cv2,np
        self.context_path=Path(model_path).parent/'context'
        self.context_enabled=context_enabled and (self.context_path/'helicopter.onnx').exists() and (self.context_path/'pistol.onnx').exists()
        self.context_models=None;self.context_error=''
        self.weapon_context_enabled=True
        cv2.setNumThreads(1)
        from .inference import create_session
        self.session,self.backend=create_session(model_path)
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.height,self.width = int(inp.shape[2]),int(inp.shape[3])
        grid_parts,stride_parts = [],[]
        for stride in (8,16,32):
            gh,gw = self.height//stride,self.width//stride
            ys,xs = np.indices((gh,gw))
            grid_parts.append(np.column_stack((xs.ravel(),ys.ravel())))
            stride_parts.append(np.full((gh*gw,1),stride,dtype=np.float32))
        self.grid = np.concatenate(grid_parts).astype(np.float32)
        self.strides = np.concatenate(stride_parts)

    def detect_rgb(self,pixels,width,height,threshold=.30,recover_down=False):
        began=time.perf_counter()
        normal,inference_ms,total_ms=self._detect_rgb(pixels,width,height,threshold)
        rgb=self.np.frombuffer(pixels,dtype=self.np.uint8).reshape(height,width,3)
        if recover_down:
            proposals=[]
            for turns in (1,3):
                rotated=self.np.ascontiguousarray(self.np.rot90(rgb,turns));h,w=rotated.shape[:2]
                found,elapsed,_=self._detect_rgb(rotated.tobytes(),w,h,.45)
                inference_ms+=elapsed
                proposals.extend((d,turns) for d in found if d.label=='person')
            normal=merge_down_proposals(normal,proposals,width,height)
        if getattr(self,'context_enabled',False):normal=self._context(rgb,normal)
        return normal,inference_ms,(time.perf_counter()-began)*1000

    def _context(self,rgb,detections):
        try:
            if self.context_models is None:
                from .context import GunDetector,HelicopterDetector
                self.context_models=(GunDetector(self.context_path/'pistol.onnx'),HelicopterDetector(self.context_path/'helicopter.onnx'))
            gun,helicopter=self.context_models
            hints=tuple(ObjectHint('pistol',d.confidence,d.box) for d in gun.detect(rgb,.18)) if self.weapon_context_enabled else ()
            result=[];budget=2
            for d in detections:
                weapons=[]
                if d.label=='person' and self.weapon_context_enabled:
                    a,b,c,e=d.box;bw,bh=c-a,e-b
                    weapons=[h for h in hints if a-bw*.25<=(h.box[0]+h.box[2])/2<=c+bw*.25 and b<=(h.box[1]+h.box[3])/2<=b+bh*.8]
                    if not weapons and budget>0 and bh*rgb.shape[0]>70:
                        weapons=list(gun.for_person(rgb,d.box));budget-=1
                result.append(replace(d,weapon_boxes=tuple(h.box for h in weapons),weapon_scores=tuple(h.confidence for h in weapons)))
            airborne=helicopter.detect(rgb)
            # Keep explicit helicopter classes separate from COCO cars. No
            # relabeling an airplane/car to claim helicopter recognition.
            return tuple(result)+airborne
        except Exception as exc:
            self.context_error=str(exc);self.context_enabled=False
            return detections

    def _detect_rgb(self,pixels,width,height,threshold=.30):
        cv2,np = self.cv2,self.np
        began = time.perf_counter()
        rgb = np.frombuffer(pixels,dtype=np.uint8).reshape(height,width,3)
        bgr = cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
        ratio = min(self.width/width,self.height/height)
        resized = cv2.resize(bgr,(int(width*ratio),int(height*ratio)))
        padded = np.full((self.height,self.width,3),114,dtype=np.uint8)
        padded[:resized.shape[0],:resized.shape[1]] = resized
        tensor = np.ascontiguousarray(padded.transpose(2,0,1)[None],dtype=np.float32)
        infer_start = time.perf_counter()
        output = self.session.run(None,{self.input_name:tensor})[0][0]
        inference_ms = (time.perf_counter()-infer_start)*1000
        if output.shape != (len(self.grid),85):
            raise ValueError(f"不支持的模型输出形状：{output.shape}")
        centers = (output[:,:2]+self.grid)*self.strides
        extents = np.exp(np.clip(output[:,2:4],-20,20))*self.strides
        class_ids = output[:,5:].argmax(axis=1)
        scores = output[:,4]*output[np.arange(len(output)),5+class_ids]
        prop_labels={39:'bottle',40:'glass',41:'cup',67:'phone',56:'chair',57:'couch'}
        prop_indexes=np.flatnonzero((scores>=.40)&np.isin(class_ids,list(prop_labels)))
        hints=[]
        from .tracking import overlap
        for index in sorted(prop_indexes,key=lambda i:float(scores[i]),reverse=True):
            raw=np.r_[centers[index]-extents[index]/2,centers[index]+extents[index]/2]/ratio/[width,height,width,height]
            box=tuple(float(v) for v in np.clip(raw,0,1))
            hint=ObjectHint(prop_labels[int(class_ids[index])],float(scores[index]),box)
            if not any(h.label==hint.label and overlap(h.box,box)>.45 for h in hints):
                hints.append(hint)
            if len(hints)>=8:break
        labels = {0:"person",2:"car",3:"motorcycle",5:"bus",7:"truck",8:"boat",16:"dog"}
        selected = (scores>=threshold)&np.isin(class_ids,list(labels))
        centers,extents,scores,class_ids = centers[selected],extents[selected],scores[selected],class_ids[selected]
        corners = np.column_stack((centers-extents/2,centers+extents/2))/ratio
        unclipped=corners.copy()
        if len(corners):
            corners[:,[0,2]] = np.clip(corners[:,[0,2]],0,width)
            corners[:,[1,3]] = np.clip(corners[:,[1,3]],0,height)
        detections = []
        for cid,label in labels.items():
            candidates = np.flatnonzero(class_ids==cid)
            if not len(candidates):
                continue
            boxes = corners[candidates]
            xywh = np.column_stack((boxes[:,:2],boxes[:,2:]-boxes[:,:2]))
            keep = cv2.dnn.NMSBoxes(xywh.tolist(),scores[candidates].tolist(),threshold,.45)
            for local in np.asarray(keep,dtype=int).ravel():
                index = candidates[local]
                x1,y1,x2,y2 = corners[index]
                if x2-x1<2 or y2-y1<2:
                    continue
                detections.append(Detection(label,float(scores[index]),
                    (float(x1/width),float(y1/height),float(x2/width),float(y2/height)),
                    render_box=tuple(float(v) for v in unclipped[index]/[width,height,width,height])))
        detections.sort(key=lambda item:item.confidence,reverse=True)
        kept = []
        people,vehicles,dogs = 0,0,0
        for det in detections:
            if det.label=="person" and people<MAX_PEOPLE:
                if any(person_fragment(det,other) for other in kept):
                    continue
                kept.append(det)
                people += 1
            elif det.label=='dog':
                if dogs<MAX_DOGS:
                    kept.append(det)
                    dogs+=1
            elif det.label!="person" and vehicles<MAX_VEHICLES:
                from .tracking import overlap
                if any(other.label not in ('person','dog') and overlap(det.box,other.box)>.65 for other in kept):
                    continue  # car/bus/truck votes for the same visible vehicle
                kept.append(det)
                vehicles += 1
        return attach_object_hints(kept,hints),inference_ms,(time.perf_counter()-began)*1000


class DetectionWorker:
    def __init__(self,model_path,analysis_enabled=True):
        self.model_path = Path(model_path)
        self.analysis_enabled=analysis_enabled
        self.results = queue.Queue(maxsize=2)
        self.events = queue.Queue(maxsize=8)
        self._condition = threading.Condition()
        self._pending = None
        self._epoch = 0
        self._tracking_revision=0
        self._down_recovery=False
        self.weapon_context_enabled=True
        self._closed = False
        self._thread = threading.Thread(target=self._run,name="object-detection",daemon=True)
        self._thread.start()

    @property
    def epoch(self):
        with self._condition:
            return self._epoch

    def reset(self,preserve_tracking=False):
        with self._condition:
            self._epoch += 1
            if not preserve_tracking:
                self._tracking_revision+=1
            self._pending = None
            self._condition.notify_all()

    def set_model(self,model_path):
        with self._condition:
            self.model_path=Path(model_path)
            self._epoch+=1
            self._tracking_revision+=1
            self._pending=None
            self._condition.notify_all()

    def submit(self,frame):
        with self._condition:
            self._pending = (self._epoch,self._tracking_revision,self.model_path,frame,self._down_recovery)
            self._condition.notify_all()

    def set_down_recovery(self,enabled):
        with self._condition:
            self._down_recovery=bool(enabled)
            self._epoch+=1;self._pending=None

    def close(self):
        with self._condition:
            self._closed = True
            self._epoch += 1
            self._condition.notify_all()

    @staticmethod
    def _latest(target,value):
        try:
            target.put_nowait(value)
        except queue.Full:
            try:
                target.get_nowait()
            except queue.Empty:
                pass
            target.put_nowait(value)

    def _run(self):
        detector = None
        analyzer = None
        analysis_epoch = None
        loaded_path = None
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._closed or self._pending is not None)
                if self._closed:
                    return
                epoch,tracking_revision,model_path,frame,recover_down = self._pending
                self._pending = None
            try:
                if detector is None or loaded_path!=model_path:
                    self._latest(self.events,(epoch,"loading","正在加载本地模型……"))
                    detector = YoloXDetector(model_path)
                    loaded_path=model_path
                if epoch!=self.epoch:
                    continue
                began=time.perf_counter()
                detector.weapon_context_enabled=self.weapon_context_enabled
                if recover_down:
                    detections,inference_ms,total_ms = detector.detect_rgb(frame.pixels,frame.width,frame.height,recover_down=True)
                else:
                    detections,inference_ms,total_ms = detector.detect_rgb(frame.pixels,frame.width,frame.height)
                horizon=None
                if self.analysis_enabled:
                    if analyzer is None:
                        from .vision import SceneAnalyzer
                        analyzer=SceneAnalyzer(model_path.parent)
                    if analysis_epoch!=tracking_revision:
                        analyzer.reset()
                        analysis_epoch=tracking_revision
                    detections,horizon=analyzer.analyze(frame,detections)
                total_ms=max(total_ms,(time.perf_counter()-began)*1000)
                if epoch==self.epoch:
                    self._latest(self.results,DetectionResult(epoch,frame.generation,frame.timestamp,detections,
                                                              inference_ms,total_ms,detector.backend,horizon,analyzer.revision if analyzer else 0))
            except Exception as exc:
                if epoch==self.epoch:
                    self._latest(self.events,(epoch,"error",str(exc)))
