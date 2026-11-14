"""Sample availability on a continuous driving shot; no screenshot upload."""
from pathlib import Path
import sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1];out=base.parent/'20_闪白修复验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
position=float(sys.argv[2]) if len(sys.argv)>2 else 517
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=position)
app.ai_var.set(True);app.down_recovery_var.set(True);app._down_recovery_changed()
app.shading_var.set(True);app.sky_var.set(True);app.road_var.set(True);app._road_changed()
started=time.perf_counter();samples=[];playing=None
def sample():
    global playing
    try:
        now=time.perf_counter()
        if playing is None:
            assert now-started<30
            if app._environment_is_current() and app._detection_is_current():playing=now;app.start()
        else:
            env=app._environment_is_current();det=app._detection_is_current()
            samples.append(dict(wall=round(now-playing,3),media=app.video_position,environment=env,actors=det,
                displayed_background=bool(app.output_canvas.find_withtag('shade-background')),
                environment_age=round(app.video_position-app.road_result.timestamp,3) if app.road_result else None,
                detection_age=round(app.video_position-app.detection_result.timestamp,3) if app.detection_result else None,
                generation=app.video.generation,revision=app._last_scene_revision))
            if now-playing>=8:
                app.pause()
                transitions=sum(a['environment']!=b['environment'] for a,b in zip(samples,samples[1:]))
                report=dict(passed=True,samples=len(samples),environment_absent=sum(not r['environment'] for r in samples),
                    environment_transitions=transitions,fully_unavailable=sum(not r['environment'] and not r['actors'] for r in samples),
                    displayed_background_absent=sum(not r['displayed_background'] for r in samples),
                    actor_status=app.ai_status_var.get(),environment_status=app.road_status_var.get(),records=samples)
                name=sys.argv[1] if len(sys.argv)>1 else 'flicker-before.json'
                (out/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print({k:v for k,v in report.items() if k!='records'},flush=True);app.close();return
        app.after(35,sample)
    except Exception:app._smoke_failure()
app.after(100,sample);app.mainloop();sys.exit(1 if app.test_failed else 0)
