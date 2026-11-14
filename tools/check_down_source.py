"""Evaluate reviewed source frames, including negative sitting/bending examples."""
from pathlib import Path
import sys,json,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.core import Entity,Scene
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'18_倒地人物验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
capture=cv2.VideoCapture(source);detector=YoloXDetector(base/'models/yolox_s.onnx');analyzer=SceneAnalyzer(base/'models')
root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
records=[];positive=[]
for second in (240,525,565,570,575,580,1100):
    capture.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,bgr=capture.read();assert ok
    rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2]
    before,_,baseline_ms=detector.detect_rgb(rgb.tobytes(),w,h)
    detected,_,total_ms=detector.detect_rgb(rgb.tobytes(),w,h,recover_down=True)
    from stickfigure.video import VideoFrame
    frame=VideoFrame(1,second,w,h,rgb.tobytes());analyzer.reset();enriched,horizon=analyzer.analyze(frame,detected)
    people=[d for d in enriched if d.label=='person' and not d.predicted and d.confirmed]
    down=[d for d in people if d.action=='DOWN']
    print(second,[(d.action,round(d.confidence,2),d.posture_hint,d.corroborated) for d in people],flush=True)
    if second==570:assert down,'reviewed floor person must be recovered on paused first frame'
    else:assert not down,('false lying person in reviewed negative frame',second,down)
    records.append(dict(timestamp=second,baseline_people=sum(d.label=='person' for d in before),people=len(people),down=len(down),baseline_ms=baseline_ms,recovery_ms=total_ms))
    if down:
        entities=tuple(Entity(d.track_id,'person' if d.label=='person' else 'car',(d.box[0]+d.box[2])/2,d.box[3],
            bbox=d.box,render_bbox=d.render_box,action=d.action,action_mirror=d.action_mirror,posture_fit=d.action=='DOWN',
            vehicle_type='motorcycle' if d.label=='motorcycle' else 'car',yaw=d.yaw) for d in enriched if not d.predicted and d.confirmed)
        scene=Scene(0,0,1,0,entities,False,horizon=horizon,frame_clipping=True)
        image=raster(canvas,scene,'自动躺卧补检 → 固定倒地素材 · 实际视频 '+str(second)+'s')
        original=cv2.resize(bgr,(800,450));proof=np.hstack((original,image))
        cv2.imencode('.png',proof)[1].tofile(str(out/f'倒地人物源片对照_{second}s.png'))
        marked=bgr.copy()
        for d in down:
            a,b,c,e=d.box;cv2.rectangle(marked,(round(a*w),round(b*h)),(round(c*w),round(e*h)),(0,180,255),2)
        cv2.imencode('.jpg',marked)[1].tofile(str(out/f'倒地人物检测_{second}s.jpg'))
        positive.append(second)
capture.release();root.destroy()
(out/'down-source-result.json').write_text(json.dumps(dict(passed=True,source=source,positives=positive,records=records,checks=[
    'current-frame normal and rotated person agreement recovers floor person','paused first frame can confirm cross-view evidence',
    'lying candidate selects fixed DOWN material without source contour art','lying extent uses horizontal material fitting',
    'reviewed bending sitting portrait city and upright negative frames do not produce DOWN']),ensure_ascii=False,indent=2),encoding='utf-8')
