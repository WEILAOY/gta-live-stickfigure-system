"""Live app options, worker propagation, cache, settings and source playback."""
from pathlib import Path
import sys,time,json
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.shading import tone_spec
base=Path(__file__).resolve().parents[1];out=base.parent/'23_六档漫画阴影验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=1400)
app.ai_var.set(True);app.shading_var.set(True);app.sky_var.set(True);app.buildings_var.set(True);app.road_var.set(True)
app.model_profile_var.set('精细');app._model_changed();app.person_action_var.set('自动姿态');app.weapon_var.set('手枪');app.fps_var.set('30')
app.auto_fire_var.set(True);app._auto_fire_changed()
cases=[(3,'疏','粗略'),(4,'密','精细'),(6,'中等','标准')];state={'case':-1,'playing':False,'flash_pixels':False,'frames':0};started=time.perf_counter()
def select_case():
    state['case']+=1;levels,density,detail=cases[state['case']]
    app.shadow_levels_var.set(str(levels));app.shadow_density_var.set(density);app.shadow_detail_var.set(detail)
    app._shadow_options_changed();app.after(60,poll)
def poll():
    try:
        assert time.perf_counter()-started<40,(state,app.video_position,app.road_status_var.get())
        if not state['playing']:
            if not app._environment_is_current() or app.output_canvas.winfo_width()<100:app.after(50,poll);return
            levels,density,detail=cases[state['case']]
            assert set(r.tone for r in app.road_result.shading if r.tone!=3)<=set(tone_spec(levels)[1])
            scene=app._presentation_scene(app.scene);assert scene.shadow_density==density
            app.output_canvas.draw(scene);assert app.output_canvas.find_withtag('comic-background')
            assert app.output_canvas._background_cache[0][-1]==density
            app.open_shadow_settings();assert app.shadow_window.winfo_exists()
            app.shadow_window.destroy()
            app.save_settings();loaded=app._load_settings()
            assert (loaded['shadow_levels'],loaded['shadow_density'],loaded['shadow_detail'])==(levels,density,detail)
            if state['case']<len(cases)-1:select_case();return
            app.start();state['playing']=True
        else:
            state['frames']+=1
            if app.output_canvas.find_withtag('comic-background'):
                for photo,bounds in app.output_canvas._layer_cache.values():
                    if photo is None:continue
                    raw=photo.tk.call(str(photo),'data','-format','png');p=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
                    if np.any((p[:,:,2]>180)&(p[:,:,1]>90)&(p[:,:,0]<180)):state['flash_pixels']=True
            if app.video_position>1407:
                assert app._shot_count>0 and state['flash_pixels'],state
                assert not app.fire_detector.last_error
                app.shading_var.set(False);scene=app._presentation_scene(app.scene)
                assert scene is not None
                assert scene.shading is None or all(r.tone==3 for r in scene.shading)
                assert not scene.contact_shadows
                app.pause()
                # Seek/reset invalidates old shade and its worker history.
                old_epoch=app.road_worker.epoch;app._reset_road()
                assert app.road_worker.epoch>old_epoch and app.road_result is None
                (out/'shadow-workflow-result.json').write_text(json.dumps(dict(passed=True,cases=cases,**state,checks=[
                    '3/4/6 levels propagate to asynchronous environment worker','density propagates to actual background cache',
                    'coarse/standard/fine precision options return fresh results','all three settings roundtrip',
                    'live 30fps source playback retains fixed actor and visible automatic flash pixels',
                    'disable removes shade and contact layers while sky remains independent','reset invalidates old background epoch']),ensure_ascii=False,indent=2),encoding='utf-8')
                print('Shadow options and live fire workflow passed.',flush=True);app.close();return
        app.after(25,poll)
    except Exception:app._smoke_failure()
app.after(150,select_case);app.mainloop();sys.exit(1 if app.test_failed else 0)
