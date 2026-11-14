"""Real video comic/sky proof, manual transport materials and settings."""
from pathlib import Path
import sys,json,time
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.core import Entity,Scene
from stickfigure.rendering import SceneCanvas
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'17_载具与漫画阴影验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=525)
app.ai_var.set(True);app.shading_var.set(True);app.sky_var.set(True);app.road_var.set(True);app.buildings_var.set(True)
app.vehicle_model_var.set('自动类别');app.person_action_var.set('自动姿态')
app.shadow_mode_var.set('分区+投影');app._detection_changed();app._road_changed()
started=time.perf_counter();records=[];tiles=[];stage=0

def ready():
    global stage,started
    try:
        assert time.perf_counter()-started<35,(stage,app.road_status_var.get(),app.ai_status_var.get())
        if not app._environment_is_current() or app.road_result.shading is None:
            app.after(100,ready);return
        if stage<2 and not (app.scene and app.scene.entities):app.after(100,ready);return
        scene=app._presentation_scene(app.scene)
        assert scene.shading is not None
        if stage<2:
            if stage==0:assert any(r.tone==3 for r in scene.shading),'visible sky should be segmented'
            app.output_canvas.draw(scene,simulated=False)
            assert app.output_canvas.find_withtag('comic-background') and app.output_canvas.find_withtag('preset-object')
            import tkinter as tk
            window=tk.Toplevel(app);window.geometry('800x450');canvas=SceneCanvas(window);canvas.pack(fill='both',expand=True);window.update()
            image=raster(canvas,scene,'漫画排线 / 网点 + 淡蓝天空 · 实际视频 '+str(round(app.video_position))+'s')
            rgb=np.frombuffer(app.video_frame.pixels,np.uint8).reshape(app.video_frame.height,app.video_frame.width,3)
            original=cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),(800,450))
            proof=np.hstack((original,image));cv2.imencode('.png',proof)[1].tofile(str(out/f'漫画阴影_{round(app.video_position)}s.png'))
            tiles.append(cv2.resize(proof,(1280,360)));window.destroy()
            records.append(dict(timestamp=app.video_position,sky_regions=sum(r.tone==3 for r in scene.shading),shadow_regions=sum(r.tone!=3 for r in scene.shading),actors=len(scene.entities),environment_ms=app.road_result.total_ms))
            if stage==0:
                stage=1;started=time.perf_counter();app.seek_video(1100);assert app.road_result is None
                app.after(100,ready);return
            app.ai_var.set(False);app._detection_changed();app.road_var.set(False);app.buildings_var.set(False);app.shading_var.set(False);app._road_changed()
            assert app._environment_enabled();stage=2;started=time.perf_counter();app.after(100,ready);return
        if stage==2:
            assert not scene.entities and all(r.tone==3 for r in scene.shading) and not scene.contact_shadows
            app.sky_var.set(False);app._road_changed();assert not app._environment_enabled() and app._presentation_scene(None) is None
            app.shading_var.set(True);app.shadow_mode_var.set('仅脚下投影');app._road_changed();assert not app._environment_enabled()
            app.shadow_mode_var.set('明暗分区');app._road_changed();assert app._environment_enabled()
            stage=3;started=time.perf_counter();app.after(100,ready);return
        assert all(r.tone!=3 for r in scene.shading) and not scene.contact_shadows
        # These objects are explicit material fixtures, never source detections.
        raw=Scene(0,0,999,0,(Entity('fixture','car',.5,.85,bbox=(.2,.2,.8,.85)),),False,frame_clipping=True)
        for label,material in (('汽车','car'),('摩托车','motorcycle'),('直升机','helicopter')):
            app.vehicle_model_var.set(label);presented=app._presentation_scene(raw)
            assert presented.entities[0].vehicle_type==material
            app.output_canvas.draw(presented);assert app.output_canvas.find_withtag('preset-object')
        app.tabs.select(app.appearance_tab);app.update_idletasks()
        for group,label in (('摩托车九视图','摩托车'),('直升机九视图','直升机')):
            app.gallery_mode_var.set(group);app._draw_asset_gallery();assert len(app.gallery_canvas.hitboxes)==9
            app._gallery_clicked('右侧');assert app.vehicle_model_var.get()==label and app.vehicle_view_var.get()=='右侧'
        app.sky_var.set(True);app.shadow_mode_var.set('分区+投影');app.save_settings();loaded=app._load_settings()
        assert loaded['vehicle_model']=='直升机' and loaded['sky'] and loaded['shading']
        app._restore_automatic();assert app.vehicle_model_var.get()=='自动类别'
        assert app._presentation_scene(raw).entities[0].vehicle_type=='car'
        app.save_settings()
        cv2.imencode('.png',np.vstack(tiles))[1].tofile(str(out/'实际视频漫画阴影对比.png'))
        (out/'comic-transport-workflow-result.json').write_text(json.dumps(dict(passed=True,source=source,records=records,helicopter_automatic_detection=False,checks=[
            'actual video sky semantic regions tinted pale blue','actual video dark and midtones rendered with fixed comic marks',
            'preset actors retained with native renderer','seek clears old environment','sky runs independently with people road buildings and shadows off',
            'sky toggle clears blue regions','contact-only mode needs no model when sky disabled','comic shadows work with sky disabled',
            'manual material overrides for car motorcycle helicopter','two new nine-view galleries render and select correct model',
            'vehicle model sky and comic settings roundtrip','restore automatic clears manual model override']),ensure_ascii=False,indent=2),encoding='utf-8')
        app.close()
    except Exception:app._smoke_failure()
app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
