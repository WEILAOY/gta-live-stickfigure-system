"""Real video, independently enabled shading and actual preset renderer proof."""
from pathlib import Path
import sys,json,time
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.assets import COMBAT_VIEWS
from export_v015 import raster
base=Path(__file__).resolve().parents[1];out=base.parent/'16_第三人称与黑灰白验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=525)
app.ai_var.set(True);app.shading_var.set(True);app.road_var.set(True);app.buildings_var.set(True)
app.shadow_mode_var.set('分区+投影');app._detection_changed();app._road_changed()
started=time.perf_counter();records=[];tiles=[];stage=0

def ready():
    global stage,started
    try:
        assert time.perf_counter()-started<40,(stage,app.road_status_var.get(),app.ai_status_var.get())
        if not app._environment_is_current() or app.road_result.shading is None:
            app.after(100,ready);return
        if stage<2 and not (app.scene and app.scene.entities):app.after(100,ready);return
        scene=app._presentation_scene(app.scene)
        assert scene.shading is not None and scene.contact_shadows
        if stage<2:
            actors=scene.entities;assert actors
            app.output_canvas.draw(scene,simulated=False);assert app.output_canvas.find_withtag('shade-background')
            assert app.output_canvas.find_withtag('preset-object')
            # Isolate renderer proof in a real 16:9 canvas for pixel export.
            from stickfigure.rendering import SceneCanvas
            import tkinter as tk
            window=tk.Toplevel(app);window.geometry('800x450');canvas=SceneCanvas(window);canvas.pack(fill='both',expand=True);window.update()
            image=raster(canvas,scene,'三档明暗 + 预设人车 · 视频 '+str(round(app.video_position))+'s')
            rgb=np.frombuffer(app.video_frame.pixels,np.uint8).reshape(app.video_frame.height,app.video_frame.width,3)
            original=cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),(800,450))
            proof=np.hstack((original,image));cv2.imencode('.png',proof)[1].tofile(str(out/f'视频明暗_{round(app.video_position)}s.png'))
            tiles.append(cv2.resize(proof,(1280,360)));window.destroy()
            records.append(dict(timestamp=app.video_position,regions=len(scene.shading),actors=len(actors),environment_ms=app.road_result.total_ms))
            if stage==0:
                stage=1;started=time.perf_counter();app.seek_video(1100);assert app.road_result is None
                app.after(100,ready);return
            app.ai_var.set(False);app._detection_changed();app.road_var.set(False);app.buildings_var.set(False);app._road_changed()
            assert app._environment_enabled();stage=2;started=time.perf_counter();app.after(100,ready);return
        assert not scene.entities and scene.shading is not None
        app.output_canvas.draw(scene,simulated=False);assert app.output_canvas.find_withtag('shade-background')
        app.shadow_mode_var.set('仅脚下投影');app._road_changed();assert not app._environment_enabled()
        assert app._presentation_scene(None) is None
        app.shadow_mode_var.set('明暗分区');app._road_changed();assert app._environment_enabled()
        app.shading_var.set(False);app._road_changed();assert not app._environment_enabled()
        assert app._presentation_scene(None) is None
        app.shading_var.set(True);app.shadow_mode_var.set('分区+投影');app.combat_view_var.set('侧面');app.save_settings()
        loaded=app._load_settings();assert loaded['shading'] and loaded['shadow_mode']=='分区+投影' and loaded['combat_view']=='侧面'
        app.person_action_var.set('持枪')
        from stickfigure.combat import combat_scene
        fixture=combat_scene(0)
        assert app._presentation_scene(fixture).entities[0].combat_yaw==90
        app.open_combat_preview();assert app.combat_preview.view_var is app.combat_view_var
        app.combat_view_var.set('正后方');app.combat_preview._tick();app.combat_preview.close()
        cv2.imencode('.png',np.vstack(tiles))[1].tofile(str(out/'视频黑灰白分区对比.png'))
        (out/'shading-workflow-result.json').write_text(json.dumps(dict(passed=True,source=source,records=records,checks=[
            'real video regions with semantic and detector actor exclusions','preset actors still rendered on shaded background',
            'seek clears old environment data','shading runs with people road and buildings disabled','three modes toggle independently',
            'shading disabled clears background','view and shading settings roundtrip','view selection reaches preview and manual actors',
            'preview lifecycle owned by application']),ensure_ascii=False,indent=2),encoding='utf-8')
        app.close()
    except Exception:app._smoke_failure()
app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
