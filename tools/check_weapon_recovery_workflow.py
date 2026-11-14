"""Rifle, pistol and fire negatives with the user's full analysis workload."""
from pathlib import Path
import sys,json,time
from dataclasses import replace
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from tkinter import font as tkfont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'25_持枪与开火恢复验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
cases=[('rifle',842,852),('pistol',1403.5,1408.5),('burning',959,974)]
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=842)
app.ai_var.set(True);app.model_profile_var.set('精细');app.down_recovery_var.set(True);app._model_changed();app._down_recovery_changed()
for var in (app.road_var,app.buildings_var,app.shading_var,app.sky_var,app.text_var,app.auto_fire_var,app.hud_assist_var,app.auto_weapon_var,app.action_captions_var):var.set(True)
app.fps_var.set('30');app.detect_rate_var.set('10');app.road_rate_var.set('5');app.shadow_levels_var.set('4');app.text_rate_var.set('1')
app.person_action_var.set('自动姿态');app.weapon_var.set('手枪');app.vehicle_model_var.set('自动类别');app._road_changed();app._text_changed();app._hud_changed()
index=0;records=[];state={};began=time.perf_counter()
def reset_state():
    global state
    state=dict(held=0,hold_without_flash=0,fire_pixels=0,types=set(),saved=False,started=False)
reset_state()
def export(name,scene):
    scene=replace(scene,entities=tuple(key[0] for key in app.output_canvas._layer_cache))
    pixels=raster(app.output_canvas,scene)
    image=Image.fromarray(cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(image)
    for tag in ('action-caption-background','ocr-text-background'):
        for ident in app.output_canvas.find_withtag(tag):draw.rectangle(app.output_canvas.coords(ident),fill=app.output_canvas.itemcget(ident,'fill'))
    for tag in ('action-caption','ocr-text'):
        for ident in app.output_canvas.find_withtag(tag):
            size=abs(tkfont.nametofont(app.output_canvas.itemcget(ident,'font'),root=app).actual('size'))
            draw.text(app.output_canvas.coords(ident),app.output_canvas.itemcget(ident,'text'),font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',max(1,size)),fill=app.output_canvas.itemcget(ident,'fill'))
    p=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR);frame=app.video_frame
    original=np.frombuffer(frame.pixels,np.uint8).reshape(frame.height,frame.width,3);original=cv2.cvtColor(original,cv2.COLOR_RGB2BGR)
    original=cv2.resize(original,(p.shape[1],p.shape[0]));proof=np.hstack((original,p))
    cv2.imencode('.png',proof)[1].tofile(str(out/name))
def poll():
    global index,began
    try:
        assert time.perf_counter()-began<65,(index,app.video_position,app.ai_status_var.get())
        name,start,end=cases[index]
        if not state['started']:
            if not(app.video_frame and app.detection_result and app.road_result):app.after(50,poll);return
            app.start();state['started']=True
        scene=app._presentation_scene(app.scene)
        armed=[e for e in scene.entities if e.kind=='person' and e.aim_point is not None and not e.predicted] if scene else []
        if armed:
            state['held']+=1;state['types'].update(e.weapon for e in armed)
            if any(e.action!='GUN_FIRE' for e in armed):state['hold_without_flash']+=1
        orange=0
        for key,(photo,bounds) in app.output_canvas._layer_cache.items():
            if photo is None or key[0].kind!='person' or key[0].action!='GUN_FIRE':continue
            raw=photo.tk.call(str(photo),'data','-format','png');p=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
            orange+=int(np.count_nonzero((p[:,:,2]>230)&(p[:,:,1]>130)&(p[:,:,0]<180)))
        if orange:
            state['fire_pixels']+=1
            if not state['saved'] and scene:
                export({'rifle':'14分_长枪动作与火光恢复.png','pistol':'23分_手枪动作与火光恢复.png','burning':'16分_无虚构枪械.png'}[name],scene);state['saved']=True
        if name=='burning' and app.video_position>=965 and not state['saved'] and scene:
            export('16分_无虚构枪械.png',scene);state['saved']=True
        if app.video_position>=end:
            if name!='burning':
                assert state['held']>0 and state['fire_pixels']>0 and state['hold_without_flash']>0,(name,state,app.shot_status_var.get())
                assert name in state['types'],(name,state)
            else:
                assert state['held']==0 and state['fire_pixels']==0 and app._shot_count==0,state
            records.append(dict(name=name,**{k:sorted(v) if isinstance(v,set) else v for k,v in state.items()},shot_candidates=app._shot_count,
                                detector_ms=app.detection_result.total_ms if app.detection_result else None))
            print(records[-1],flush=True)
            if index==len(cases)-1:
                (out/'weapon-recovery-workflow-result.json').write_text(json.dumps(dict(passed=True,full_workload=True,records=records,checks=[
                    'real playback with precision person detection plus down recovery, road/buildings/shading/sky and OCR',
                    'rifle and pistol both render fixed guns and actual warm muzzle-flash pixels',
                    'holding remains visible between firing events','recognized HUD selects rifle and pistol presets',
                    'burning-car clip emits no shooting and draws no fictional guns']),ensure_ascii=False,indent=2),encoding='utf-8')
                app.close();return
            index+=1;app.pause();app.seek_video(cases[index][1]);reset_state();began=time.perf_counter()
        app.after(40,poll)
    except Exception:app._smoke_failure()
app.after(150,poll);app.mainloop();sys.exit(1 if app.test_failed else 0)
