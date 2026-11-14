"""Causal analysis of the user's 23:20 segment; event positions drive presets."""
from pathlib import Path
import sys,json,tkinter as tk,time
from dataclasses import replace,asdict
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame
from stickfigure.shooting import ShotDetector
from stickfigure.core import Entity,Scene
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'22_极简战斗与自动火光验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
capture=cv2.VideoCapture(source);capture.set(cv2.CAP_PROP_POS_MSEC,1399.5*1000)
detector=YoloXDetector(base/'models/yolox_s.onnx');analyzer=SceneAnalyzer(base/'models');shots=ShotDetector();shots.set_enabled(True)
root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
events=[];latest=();tiles=[]
for i in range(300):
    ok,bgr=capture.read()
    if not ok:break
    timestamp=1399.5+i/30;rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2]
    frame=VideoFrame(1,timestamp,w,h,rgb.tobytes())
    if i%6==0:
        detected,*_=detector.detect_rgb(frame.pixels,w,h);latest,horizon=analyzer.analyze(frame,detected)
        shots.set_targets(latest,1,timestamp)
    shots.process(frame)
    while not shots.events.empty():
        event=shots.events.get_nowait();events.append(asdict(event));print(round(timestamp,3),event.owner,round(event.x,3),round(event.y,3),event.confidence,flush=True)
        entities=[]
        for d in latest:
            if d.predicted or not d.confirmed:continue
            x1,y1,x2,y2=d.box
            e=Entity(d.track_id,'person' if d.label=='person' else 'car',(x1+x2)/2,y2,bbox=d.box,render_bbox=d.render_box,action=d.action,
                     yaw=d.yaw,vehicle_type={'motorcycle':'motorcycle','truck':'truck','bus':'truck','boat':'boat'}.get(d.label,'car'))
            if d.track_id==event.owner:e=replace(e,action='GUN_FIRE',weapon='pistol',action_time=.05,aim_point=(event.x,event.y),aim_direction=(event.dx,event.dy))
            entities.append(e)
        scene=Scene(0,0,analyzer.revision,0,tuple(entities),False,horizon=horizon,frame_clipping=True)
        image=raster(canvas,scene,f'{timestamp:.3f}s · 开火候选 → 预设火光（画面/HUD辅助）')
        original=bgr.copy();cv2.circle(original,(round(event.x*w),round(event.y*h)),12,(0,220,255),1)
        proof=np.hstack((cv2.resize(original,(800,450)),image))
        cv2.imencode('.png',proof)[1].tofile(str(out/f'自动火光_{timestamp:.3f}s.png'))
        if len(tiles)<3:tiles.append(cv2.resize(proof,(1280,360)))
capture.release();root.destroy()
assert not shots.last_error,shots.last_error
assert any(1404<=e['timestamp']<=1407 for e in events),'no candidate in reviewed shooting segment'
assert not any(e['timestamp']<1403.5 for e in events),'cutscene gestures must not trigger fire'
if tiles:cv2.imencode('.png',np.vstack(tiles))[1].tofile(str(out/'23分20秒片段自动火光对比.png'))
(out/'auto-shot-source-result.json').write_text(json.dumps(dict(passed=True,source=source,events=events,frames=shots.frames,mean_flash_analysis_ms=shots.total_ms/max(1,shots.frames),
    checks=['actual 23:20 segment processed causally','person detector sampled while every decoded frame checked for visible flash',
            'image/HUD-supported firing candidates found during reviewed shooting scene','preceding cutscene gestures do not trigger',
            'only event coordinates and fixed gun/flash assets reach renderer']),ensure_ascii=False,indent=2),encoding='utf-8')
print('Source shot candidates:',len(events))
