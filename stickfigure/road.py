"""Local Cityscapes semantic road segmentation, scheduled independently with a latest-frame queue.

Weights: Xenova ONNX conversion of NVIDIA SegFormer-B0, research/evaluation
license; see models/ROAD_MODEL_LICENSE.txt. No predefined road geometry.
"""
from dataclasses import dataclass
import queue
import threading
import time
from .core import RoadGeometry,BuildingGeometry


@dataclass(frozen=True)
class RoadResult:
    epoch: int
    generation: int
    timestamp: float
    geometry: RoadGeometry
    total_ms: float
    buildings: BuildingGeometry | None = None
    backend: str = 'CPU · ONNX Runtime'
    shading: tuple | None = None
    colors: tuple | None = None


class RoadSegmenter:
    def __init__(self,path,input_size=(512,288)):
        self.input_size=input_size
        self.reset()
        import numpy as np
        import cv2
        self.np,self.cv2=np,cv2
        from .inference import create_session
        self.session,self.backend=create_session(path,dimensions=dict(batch_size=1,num_channels=3,
                                         height=input_size[1],width=input_size[0]))
        self.name=self.session.get_inputs()[0].name
        self.mean=np.array([.485,.456,.406],dtype=np.float32)
        self.std=np.array([.229,.224,.225],dtype=np.float32)

    def reset(self):
        self.previous=None
        self.previous_time=None
        self.buildings=None
        self.shading=None
        self.shading_stabilizer=None
        self.colors=None
        self.color_stabilizer=None
        self.semantic_labels=None

    def segment(self,frame):
        np,cv2=self.np,self.cv2
        began=time.perf_counter()
        rgb=np.frombuffer(frame.pixels,dtype=np.uint8).reshape(frame.height,frame.width,3)
        resized=cv2.resize(rgb,self.input_size,interpolation=cv2.INTER_LINEAR).astype(np.float32)/255
        tensor=np.ascontiguousarray(((resized-self.mean)/self.std).transpose(2,0,1)[None])
        logits=self.session.run(None,{self.name:tensor})[0][0]
        if logits.shape[0]!=19:
            raise ValueError('Unexpected road model classes')
        small=cv2.resize(logits.transpose(1,2,0),(160,90),interpolation=cv2.INTER_LINEAR)
        exp=np.exp(small-small.max(axis=2,keepdims=True))
        total=exp.sum(axis=2)
        probability=exp[:,:,0]/total
        labels=small.argmax(axis=2).astype(np.uint8)
        from .shading import extract_shading,ShadingStabilizer
        if self.previous_time is not None and (frame.timestamp<=self.previous_time or frame.timestamp-self.previous_time>1):self.reset()
        if self.shading_stabilizer is None:self.shading_stabilizer=ShadingStabilizer()
        options=getattr(self,'shading_options',(6,'标准'))
        levels,detail=options[:2]
        color_enabled=len(options)>2 and options[2] is True
        self.semantic_labels=labels
        if color_enabled:
            from .coloring import extract_colors,ColorStabilizer
            if self.color_stabilizer is None:self.color_stabilizer=ColorStabilizer()
            self.colors=extract_colors(rgb,labels,getattr(self,'exclude_boxes',()),detail,
                                       self.color_stabilizer,frame.timestamp,frame.generation)
            self.shading_stabilizer.reset()
            shading=None
        else:
            self.colors=None
            if self.color_stabilizer is not None:self.color_stabilizer.reset()
            shading=extract_shading(rgb,labels,getattr(self,'exclude_boxes',()),levels,detail,
                                   self.shading_stabilizer,frame.timestamp,frame.generation)
        from .buildings import extract_building_outlines
        # Building geometry needs more spatial detail than the curb estimator.
        detailed=cv2.resize(logits.transpose(1,2,0),(384,216),interpolation=cv2.INTER_LINEAR)
        detailed_exp=np.exp(detailed-detailed.max(axis=2,keepdims=True))
        buildings=extract_building_outlines(detailed.argmax(axis=2).astype(np.uint8),
                          detailed_exp[:,:,2]/detailed_exp.sum(axis=2))
        from .curbs import extract_curbs,driving_view
        left,right=extract_curbs(labels,probability,rgb)
        if self.previous_time is not None and (frame.timestamp<self.previous_time-.02 or frame.timestamp-self.previous_time>1):
            self.reset()
        if self.previous:
            def stabilize(edge,old):
                if not edge or not old:
                    return edge
                old_x=np.array([p[0] for p in old]);old_y=np.array([p[1] for p in old])
                return tuple((float(.70*x+.30*np.interp(y,old_y,old_x)),y)
                             if old_y[0]<=y<=old_y[-1] and abs(x-np.interp(y,old_y,old_x))<.12 else (x,y)
                             for x,y in edge)
            left,right=stabilize(left,self.previous[0]),stabilize(right,self.previous[1])
        self.previous,self.previous_time=(left,right),frame.timestamp
        visible=(labels==0)&(probability>.45)
        coverage=float(visible.mean())
        confidence=float(probability[visible].mean()) if visible.any() else 0.0
        active=driving_view(labels)
        method='左右路缘' if left and right else '单侧路缘' if left or right else '路缘证据不足'
        geometry=RoadGeometry((),coverage,confidence,left,right,active,method)
        self.buildings=buildings
        self.shading=shading
        return geometry,(time.perf_counter()-began)*1000



class RoadWorker:
    def __init__(self,path):
        self.path=path
        self.results=queue.Queue(maxsize=2)
        self.events=queue.Queue(maxsize=4)
        self._condition=threading.Condition()
        self._epoch=0
        self._pending=None
        self._closed=False
        self._thread=threading.Thread(target=self._run,name='road-segmentation',daemon=True)
        self._thread.start()

    @property
    def epoch(self):
        with self._condition:
            return self._epoch

    def reset(self):
        with self._condition:
            self._epoch+=1
            self._pending=None
            self._condition.notify_all()

    def submit(self,frame,exclude_boxes=(),shading_options=(6,'标准')):
        with self._condition:
            self._pending=(self._epoch,frame,exclude_boxes,shading_options)
            self._condition.notify_all()

    def close(self):
        with self._condition:
            self._closed=True
            self._epoch+=1
            self._condition.notify_all()

    @staticmethod
    def _latest(target,item):
        try:
            target.put_nowait(item)
        except queue.Full:
            try:
                target.get_nowait()
            except queue.Empty:
                pass
            target.put_nowait(item)

    def _run(self):
        segmenter=None
        segment_epoch=None
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._closed or self._pending is not None)
                if self._closed:
                    return
                epoch,frame,exclude_boxes,shading_options=self._pending
                self._pending=None
            try:
                if segmenter is None:
                    segmenter=RoadSegmenter(self.path)
                if segment_epoch!=epoch:
                    if hasattr(segmenter,'reset'):
                        segmenter.reset()
                    segment_epoch=epoch
                segmenter.exclude_boxes=exclude_boxes
                segmenter.shading_options=shading_options
                geometry,elapsed=segmenter.segment(frame)
                if epoch==self.epoch:
                    self._latest(self.results,RoadResult(epoch,frame.generation,frame.timestamp,geometry,elapsed,getattr(segmenter,'buildings',None),getattr(segmenter,'backend','CPU · ONNX Runtime'),getattr(segmenter,'shading',None),getattr(segmenter,'colors',None)))
            except Exception as exc:
                if epoch==self.epoch:
                    self._latest(self.events,(epoch,str(exc)))
