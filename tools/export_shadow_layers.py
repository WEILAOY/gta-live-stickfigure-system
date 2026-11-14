"""Actual preset-canvas proof and scoped timings for six-level comic shade."""
from pathlib import Path
import sys,json,time,subprocess,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.shading import extract_shading,comic_pixels,TONE_ORDER,TONE_NAMES,ShadingStabilizer
from stickfigure.core import Scene,Entity,ShadeRegion
from stickfigure.road import RoadSegmenter
from stickfigure.detection import YoloXDetector
from stickfigure.vision import SceneAnalyzer
from stickfigure.video import VideoFrame
from stickfigure.shooting import ShotDetector
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'23_六档漫画阴影验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
def label(p,text):
    im=Image.fromarray(cv2.cvtColor(p,cv2.COLOR_BGR2RGB));d=ImageDraw.Draw(im)
    d.rectangle((0,0,im.width,38),fill='white');d.text((10,8),text,font=font,fill='#34495e')
    return cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2BGR)
def entities(detections):
    result=[]
    for d in detections:
        if d.predicted or not d.confirmed:continue
        a,b,c,e=d.box
        result.append(Entity(d.track_id,'person' if d.label=='person' else 'car',(a+c)/2,e,bbox=d.box,
            render_bbox=d.render_box,action=d.action,yaw=d.yaw,action_mirror=d.action_mirror,
            vehicle_type={'motorcycle':'motorcycle','truck':'truck','bus':'truck','boat':'boat'}.get(d.label,'car'),posture_fit=d.action=='DOWN'))
    return tuple(result)
def make_frame(bgr,t,generation):
    rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);h,w=rgb.shape[:2]
    return rgb,VideoFrame(generation,t,w,h,rgb.tobytes())
def main():
    full=((0,0),(1,0),(1,1),(0,1));tiles=[]
    for tone,name in zip(reversed(TONE_ORDER),reversed(TONE_NAMES)):
        p=comic_pixels((ShadeRegion(tone,full),),640,360)
        tiles.append(label(cv2.cvtColor(p,cv2.COLOR_BGRA2BGR),name))
    cv2.imencode('.png',np.vstack((np.hstack(tiles[:3]),np.hstack(tiles[3:]))))[1].tofile(str(out/'六档预设阴影纹理.png'))
    root=tk.Tk();root.geometry('800x450');canvas=SceneCanvas(root);canvas.pack(fill='both',expand=True);root.update()
    segmenter=RoadSegmenter(base/'models/segformer_b0_cityscapes.onnx')
    detector=YoloXDetector(base/'models/yolox_s.onnx');analyzer=SceneAnalyzer(base/'models')
    samples=[];rows=[];extraction=[];draws=[];environment=[]
    for generation,(name,path,t) in enumerate((('室外城市',source,525),('驾驶',str(base.parent/'03_测试素材/gta5_test_01.mp4'),90),('室内射击',source,1405.5)),1):
        cap=cv2.VideoCapture(path);cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,bgr=cap.read();cap.release();assert ok
        rgb,frame=make_frame(bgr,t,generation);analyzer.reset();segmenter.reset()
        detected,*_=detector.detect_rgb(frame.pixels,frame.width,frame.height);detected,horizon=analyzer.analyze(frame,detected)
        boxes=tuple(d.box for d in detected if not d.predicted);segmenter.exclude_boxes=boxes
        road,elapsed=segmenter.segment(frame);environment.append(elapsed)
        old=extract_shading(rgb,segmenter.semantic_labels,boxes,levels=3,detail='粗略')
        scene=Scene(0,0,generation,0,entities(detected),False,horizon=horizon,road=road,buildings=segmenter.buildings,
                    shading=segmenter.shading,contact_shadows=True,frame_clipping=True)
        p=raster(canvas,scene,'6档 / 标准精度 / 双层脚下投影')
        before=raster(canvas,replace(scene,shading=old),'3档 / 粗略精度')
        row=np.hstack((label(cv2.resize(bgr,(800,450)),name+' · 原画面'),before,p));rows.append(cv2.resize(row,(1920,360)))
        cv2.imencode('.png',row)[1].tofile(str(out/(name+'分区对照.png')))
        samples.append(dict(name=name,timestamp=t,old_regions=len(old),new_regions=len(scene.shading),tones=sorted(set(r.tone for r in scene.shading if r.tone!=3))))
        for _ in range(8):
            began=time.perf_counter();extract_shading(rgb,segmenter.semantic_labels,boxes);extraction.append((time.perf_counter()-began)*1000)
    cv2.imencode('.png',np.vstack(rows))[1].tofile(str(out/'三类画面阴影细化对照.png'))
    # Sequential source analysis at 5Hz, output sampled at 30fps. This export is
    # an offline proof, not a claim that all analysis modules run at 30Hz.
    cap=cv2.VideoCapture(source);cap.set(cv2.CAP_PROP_POS_MSEC,1400*1000)
    analyzer.reset();segmenter.reset();shots=ShotDetector();shots.set_enabled(True);effects={};shot_count=0
    process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1600x450','-r','30','-i','pipe:0',
        '-an','-c:v','libx264','-preset','fast','-crf','20','-threads','2','-movflags','+faststart',str(out/'23分20秒_六档阴影与自动火光.mp4')],stdin=subprocess.PIPE)
    for i in range(240):
        ok,bgr=cap.read();assert ok;t=1400+i/30;rgb,frame=make_frame(bgr,t,10)
        if i%6==0:
            detected,*_=detector.detect_rgb(frame.pixels,frame.width,frame.height);detected,horizon=analyzer.analyze(frame,detected)
            boxes=tuple(d.box for d in detected if not d.predicted);segmenter.exclude_boxes=boxes
            road,elapsed=segmenter.segment(frame);environment.append(elapsed);shots.set_targets(detected,10,t)
            actors=entities(detected);shades=segmenter.shading;buildings=segmenter.buildings
        shots.process(frame)
        while not shots.events.empty():
            event=shots.events.get_nowait();effects[event.owner]=event;shot_count+=1
        output=[]
        for actor in actors:
            event=effects.get(actor.track_id)
            if event and 0<=t-event.timestamp<.6:
                age=t-event.timestamp;point=(event.x+actor.x-event.owner_center[0],event.y+actor.y-event.owner_center[1])
                actor=replace(actor,action='GUN_FIRE' if age<.12 else 'GUN_HOLD',weapon='pistol',action_time=age if age<.12 else 0,
                              aim_point=point,aim_direction=(event.dx,event.dy))
            output.append(actor)
        scene=Scene(i,0,10,t,tuple(output),False,horizon=horizon,road=road,buildings=buildings,
                    shading=shades,contact_shadows=True,frame_clipping=True)
        began=time.perf_counter();canvas.draw(scene);draws.append((time.perf_counter()-began)*1000)
        p=raster(canvas,scene,'6档漫画阴影 · 预设人车/枪械/火光')
        process.stdin.write(np.hstack((label(cv2.resize(bgr,(800,450)),f'原画面 {int(t//60):02}:{t%60:05.2f}'),p)).tobytes())
    process.stdin.close();assert process.wait()==0;cap.release();root.destroy();assert shot_count>=1
    def stats(values):return dict(mean_ms=float(np.mean(values)),p95_ms=float(np.percentile(values,95)))
    report=dict(passed=True,samples=samples,video_frames=240,video_fps=30,automatic_flash_candidates=shot_count,
        extraction=stats(extraction),canvas_draw_800x450=stats(draws),environment_model_and_geometry=stats(environment),
        note='Offline source proof. Timings are scoped modules, not end-to-end sustained frame rate. Human/model inference and export encoding are excluded from canvas timings.',
        checks=['six fixed texture materials exported','outdoor/driving/interior source comparisons','semantic sky preserved',
                'source actors excluded before coarse brightness geometry','sequential 30fps source/scene proof',
                'automatic visible-flash event stays readable over hatch background','bounded geometry and cached preset patterns'])
    (out/'shadow-export-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
