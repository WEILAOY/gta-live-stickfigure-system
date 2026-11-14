"""Deterministic delayed-result stress check on a real video surface."""
from pathlib import Path
import sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.detection import Detection,DetectionResult
from stickfigure.road import RoadResult
from stickfigure.core import RoadGeometry,ShadeRegion,RunState
base=Path(__file__).resolve().parents[1];out=base.parent/'20_闪白修复验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=517)
app.detector.submit=lambda *args:None;app.road_worker.submit=lambda *args:None
started=time.perf_counter()
def ready():
    try:
        assert time.perf_counter()-started<15
        if not app.video_frame or app.output_canvas.winfo_width()<100 or app.output_canvas.winfo_height()<100:
            app.after(50,ready);return
        app.ai_var.set(True);app.shading_var.set(True);app.sky_var.set(False)
        now=app.video_position;generation=app.video.generation
        d=Detection('car',.9,(.3,.4,.6,.8),track_id='current')
        detected=DetectionResult(app.detector.epoch,generation,now-.8,(d,),600,600,'test')
        background=RoadResult(app.road_worker.epoch,generation,now-.8,RoadGeometry(),600,
                              shading=(ShadeRegion(0,((0,0),(1,0),(1,1),(0,1))),))
        app.detector.results.put(detected);app.road_worker.results.put(background)
        app._poll_road();app._poll_detection()
        assert app._environment_is_current() and app._detection_is_current() and app.scene.entities
        app.output_canvas.draw(app._presentation_scene(app.scene))
        assert app.output_canvas.find_withtag('comic-background') and app.output_canvas.find_withtag('preset-object'),(app.output_canvas.winfo_width(),app.output_canvas.winfo_height(),app.output_canvas.find_all())
        # The next slow result is pending: a completed valid frame is not
        # cleared just because 0.48 seconds have elapsed.
        app.video_position=now+.2;app._poll_detection()
        assert app.scene and app._environment_is_current()
        # A NEW completed negative observation removes the actor immediately.
        app.detector.results.put(DetectionResult(app.detector.epoch,generation,app.video_position,(),20,20,'test'))
        app._poll_detection();assert app.scene and not app.scene.entities
        app.output_canvas.draw(app._presentation_scene(app.scene))
        assert not app.output_canvas.find_withtag('preset-object')
        # Prolonged absence still times out, never freezing indefinitely.
        app.video_position=now+3;app._poll_detection()
        assert app.scene is None and not app._environment_is_current()
        app._render_pending_since=time.perf_counter()
        assert app._waiting_for_output(time.perf_counter())
        assert not app._waiting_for_output(time.perf_counter()+2)
        app._render_pending_since=time.perf_counter();app.stop()
        assert app._render_pending_since is None and app.scene is None
        (out/'flicker-workflow-result.json').write_text(json.dumps(dict(passed=True,checks=[
            '600ms delayed results accepted instead of background expiring at 480ms','valid pending analysis keeps current completed scene',
            'new completed negative observation removes actor immediately','prolonged absence expires at bounded timeout',
            'pause/resume transition wait is bounded','stop clears pending transition']),ensure_ascii=False,indent=2),encoding='utf-8')
        app.close()
    except Exception:app._smoke_failure()
app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
