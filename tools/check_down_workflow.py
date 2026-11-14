"""Actual paused video, current-evidence DOWN, seek, manual override and toggle."""
from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1];out=base.parent/'18_倒地人物验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=570)
app.ai_var.set(True);app.down_recovery_var.set(True);app.person_action_var.set('自动姿态');app._down_recovery_changed()
started=time.perf_counter();stage=0;records=[]
def ready():
    global started,stage
    try:
        assert time.perf_counter()-started<25,(stage,app.ai_status_var.get())
        if not (app.scene and app.detection_result and app._detection_is_current()):app.after(100,ready);return
        scene=app._presentation_scene(app.scene);down=[e for e in scene.entities if e.action=='DOWN']
        if stage in (0,3):
            assert down and all(e.posture_fit and not e.predicted for e in down)
            assert all(e.action_time is None for e in down)
            app.output_canvas.draw(scene,simulated=False)
            material=[(k,p) for k,p in app.output_canvas._layer_cache.items() if k[0].action=='DOWN']
            assert material and all(p[0] is not None for _,p in material)
            records.append(dict(stage=stage,position=app.video_position,down=len(down),inference_ms=app.detection_result.total_ms))
            if stage==0:
                app.start();app._down_play_started=time.perf_counter();app.after(200,played);return
            app.save_settings();assert app._load_settings()['down_recovery']
            (out/'down-workflow-result.json').write_text(json.dumps(dict(passed=True,records=records,checks=[
                'paused first frame recovers a currently observed floor person','automatic DOWN uses horizontal preset fitting',
                'actual renderer produces a visible DOWN material layer','playback accepts multiple analyzed frames',
                'predicted or missing people never become drawable DOWN ghosts','seek invalidates old generation and posture',
                'sitting frame does not become DOWN','manual DOWN remains explicit standing-anchor material',
                'turning recovery off removes recovered DOWN','turning on while paused redetects and restores DOWN',
                'recovery setting roundtrip']),ensure_ascii=False,indent=2),encoding='utf-8')
            app.close();return
        if stage==1:
            assert not down
            app.person_action_var.set('倒地');manual=app._presentation_scene(app.scene)
            assert all(not e.posture_fit and e.action_time is not None for e in manual.entities if e.kind=='person')
            app._restore_automatic();app.down_recovery_var.set(False);app._down_recovery_changed();app.seek_video(570)
            stage=2;started=time.perf_counter();app.after(100,ready);return
        assert not down
        epoch=app.detector.epoch;app.down_recovery_var.set(True);app._down_recovery_changed()
        assert app.detector.epoch!=epoch and app.scene is None
        stage=3;started=time.perf_counter();app.after(100,ready)
    except Exception:app._smoke_failure()
def played():
    global started,stage
    try:
        if len(app._accepted_detection_times)<3:
            assert time.perf_counter()-app._down_play_started<8,app.ai_status_var.get()
            app.after(150,played);return
        app.pause()
        if app.scene:
            displayed=app._presentation_scene(app.scene)
            ids={d.track_id for d in app.detection_result.detections if not d.predicted and d.confirmed}
            assert all(e.track_id in ids and not e.predicted for e in displayed.entities)
        app.seek_video(575);assert app.scene is None and app.detection_result is None
        stage=1;started=time.perf_counter();app.after(100,ready)
    except Exception:app._smoke_failure()
app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
