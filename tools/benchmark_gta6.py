"""Review actual GTA6-labelled source frames and fixed material output."""
from pathlib import Path
import sys,json,time,collections,tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame
from stickfigure.core import Scene,Entity
from stickfigure.rendering import SceneCanvas

base=Path(__file__).resolve().parents[1];out=base.parent/'13_GTA6动作验证'
source=json.loads((out/'source-info.json').read_text(encoding='utf-8'))['source']
cap=cv2.VideoCapture(source);detector=YoloXDetector(base/'models/yolox_s.onnx');analyzer=SceneAnalyzer(base/'models')
root=tk.Tk();root.geometry('852x480');canvas=SceneCanvas(root,width=852,height=480);canvas.pack(fill='both',expand=True);root.update()
records=[];counts=collections.Counter()
for second,observed in ((220,'conversation'),(240,'holding phone'),(305,'extended arm'),(540,'bridge climbing'),
                        (660,'seated conversation'),(720,'forward arms'),(1040,'weight lifting'),(1050,'rowing'),
                        (1060,'drink / social'),(1100,'conversation gestures'),(1400,'embrace / sway'),(1430,'holding phone'),
                        (1450,'body interaction'),(1500,'forward arms'),(1560,'seated gestures')):
    analyzer.reset();samples=[]
    for delta in (-.6,-.4,-.2,0):
        cap.set(cv2.CAP_PROP_POS_MSEC,(second+delta)*1000);ok,image=cap.read();assert ok
        h,w=image.shape[:2];frame=VideoFrame(1,second+delta,w,h,cv2.cvtColor(image,cv2.COLOR_BGR2RGB).tobytes())
        raw,infer,total=detector.detect_rgb(frame.pixels,w,h)
        began=time.perf_counter();detections,horizon=analyzer.analyze(frame,raw)
        samples.append(dict(timestamp=frame.timestamp,people=[dict(id=d.track_id,action=d.action,mirror=d.action_mirror,
                               confirmed=d.confirmed,score=d.confidence,predicted=d.predicted,box=d.box,
                               hints=[dict(label=o.label,score=o.confidence,box=o.box) for o in d.object_hints])
                               for d in detections if d.label=='person'],detection_ms=total,analysis_ms=(time.perf_counter()-began)*1000))
    entities=tuple(Entity(d.track_id,'person' if d.label=='person' else 'car',(d.box[0]+d.box[2])/2,d.box[3],
                         bbox=d.box,render_bbox=d.render_box,action=d.action,action_mirror=d.action_mirror,
                         yaw=d.yaw,pose=d.pose) for d in detections if not d.predicted and d.confirmed)
    scene=Scene(1,time.perf_counter(),1,second,entities,False,horizon=horizon,frame_clipping=True)
    canvas.draw(scene,simulated=False)
    rendered=np.full((h,w,3),(252,249,247),np.uint8)
    cv2.line(rendered,(0,round(horizon.left*h)),(w-1,round(horizon.right*h)),(170,152,131),1)
    for photo,bounds in canvas._layer_cache.values():
        if photo is None:continue
        data=photo.tk.call(str(photo),'data','-format','png');pixels=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_UNCHANGED)
        x1,y1,x2,y2=bounds;alpha=pixels[:,:,3:4]/255
        rendered[y1:y2,x1:x2]=(pixels[:,:,:3]*alpha+rendered[y1:y2,x1:x2]*(1-alpha)).astype(np.uint8)
    for entity in entities:
        if entity.kind=='person':counts[entity.action]+=1
    action_text=', '.join(e.action for e in entities if e.kind=='person') or 'no confirmed people'
    combined=np.hstack((image,rendered));combined=cv2.copyMakeBorder(combined,55,0,0,0,cv2.BORDER_CONSTANT,value=(30,30,30))
    cv2.putText(combined,f'{second}s {observed} | SOURCE / AUTO FIXED MATERIAL OUTPUT',(12,22),cv2.FONT_HERSHEY_SIMPLEX,.65,(235,235,235),1,cv2.LINE_AA)
    cv2.putText(combined,action_text,(12,44),cv2.FONT_HERSHEY_SIMPLEX,.6,(130,220,220),1,cv2.LINE_AA)
    cv2.imencode('.jpg',combined)[1].tofile(str(out/f'auto_{second:04}.jpg'))
    records.append(dict(second=second,observed_scene=observed,automatic_actions=[e.action for e in entities if e.kind=='person'],samples=samples))
root.destroy();cap.release()
report=dict(passed=True,backend=detector.backend,frame_count=len(records),automatic_action_counts=dict(counts),
            note='15 reviewed moments; each uses four real preceding frames, not repeated images. Auto-rendered action categories are not manual scene labels or accuracy ground truth. Roads/buildings omitted only in these action comparison artifacts.',frames=records)
(out/'gta6-action-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(counts=counts,backend=detector.backend),ensure_ascii=False))
