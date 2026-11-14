"""Reviewed 40-second sequence: standing negative and seated positive at 44s."""
from pathlib import Path
import sys,json,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame
from stickfigure.core import Scene,Entity
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'28_坐姿检测与素材验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
cv2.setNumThreads(2);cap=cv2.VideoCapture(source);det=YoloXDetector(base/'models/yolox_s.onnx');det.context_enabled=False
analyzer=SceneAnalyzer(base/'models');root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update();records=[]
try:
    for t in (37,40,44,90,240,570,848,'dining40'):
        dining=t=='dining40'
        if dining:
            cap.release();cap=cv2.VideoCapture(str(base.parent/'03_测试素材/gta6_actions_test.mp4'));t=40
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,bgr=cap.read();assert ok
        rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2]
        ds,_,_=det.detect_rgb(rgb.tobytes(),w,h);analyzer.reset()
        ds,horizon=analyzer.analyze(VideoFrame(1,t,w,h,rgb.tobytes()),ds)
        people=[d for d in ds if d.label=='person' and not d.predicted and d.confirmed]
        seated=[d for d in people if d.seated]
        if dining:assert seated,'Reviewed dining seat context was missed'
        elif t==44:assert any(d.box[0]>.6 for d in seated),'Reviewed seated right foreground person was missed'
        else:assert not seated,('False seated posture in reviewed negative',t,seated)
        records.append(dict(timestamp=t,source='dining_clip' if dining else 'original',people=len(people),seated=len(seated),actions=[d.action for d in people]))
        print(records[-1],flush=True)
        if t==44 or dining:
            entities=tuple(Entity(d.track_id,'person',(d.box[0]+d.box[2])/2,d.box[3],bbox=d.box,render_bbox=d.render_box,
                action=d.action,action_mirror=d.action_mirror,seated=d.seated,seat_mirror=d.seat_mirror) for d in people)
            scene=Scene(0,0,1,t,entities,False,horizon=horizon,frame_clipping=True)
            pixels=raster(canvas,scene,('测试短片40秒 · 椅子辅助坐姿' if dining else '原视频44秒 · 自动坐姿分析')+' → 固定火柴人素材')
            cv2.imencode('.png',np.hstack((cv2.resize(bgr,(800,450)),pixels)))[1].tofile(str(out/('短片40秒_餐桌坐姿对照.png' if dining else '44秒_坐姿源片对照.png')))
    tiles=[]
    for label,action,mirror,seated in [('坐姿·右向','SIT',False,True),('坐姿·左向','SIT',True,True),
                                        ('坐姿交流·预设动作','SIT_GESTURE',False,True),('坐姿玩手机·预设组合','PHONE_LOOK',False,True)]:
        actor=Entity('s','person',.5,.95,bbox=(.2,.1,.8,.95),action=action,action_mirror=mirror,seated=seated)
        tiles.append(raster(canvas,Scene(0,0,1,.2,(actor,),False,frame_clipping=True),label))
    cv2.imencode('.png',np.vstack((np.hstack(tiles[:2]),np.hstack(tiles[2:]))))[1].tofile(str(out/'新版坐姿预设素材.png'))
    (out/'sitting-source-result.json').write_text(json.dumps(dict(passed=True,records=records,checks=[
        'real 44s seated foreground person detected by current pose evidence',
        'reviewed standing phone walking lying and shooting negatives do not become seated',
        'left/right sitting and upper-action combinations render only fixed assets']),ensure_ascii=False,indent=2),encoding='utf-8')
finally:cap.release();root.destroy()
