"""Comparable full-feature desktop playback measurements, not OBS capture."""
from pathlib import Path
import sys,json,time,statistics
base=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
sys.path.insert(0,str(base))
from stickfigure.app import Application
source=json.loads((Path(__file__).resolve().parents[2]/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class App(Application):
    def _run_smoke(self):pass
app=App(base,smoke_test=True,initial_video=source,initial_position=842)
app.model_profile_var.set('精细');app._model_changed()
app.down_recovery_var.set(True);app._down_recovery_changed()
for v in (app.ai_var,app.road_var,app.buildings_var,app.shading_var,app.sky_var,app.text_var,app.auto_fire_var,app.hud_assist_var,app.auto_weapon_var):v.set(True)
app.person_action_var.set('自动姿态');app.fps_var.set('30');app.detect_rate_var.set('10');app.road_rate_var.set('5');app.text_rate_var.set('1');app.shadow_levels_var.set('4')
app._road_changed();app._text_changed();app._hud_changed()
samples=[];frames=set();start=None;last=None;position=0;deadline=time.perf_counter()+40
def poll():
    global start,last,position
    try:
        now=time.perf_counter()
        assert now<deadline,'Playback did not become ready'
        if start is None:
            if app.detection_result and app.video_frame:
                app.start();start=now;last=now;position=app.video_position
        else:
            if now-start>2:
                samples.append((now-last)*1000)
                if app.video_frame:frames.add(app.video_frame.timestamp)
            last=now
            if now-start>=12:
                data=dict(full_workload=True,wall_seconds=now-start,video_seconds=app.video_position-position,
                    observed_preview_hz=len(frames)/(now-start-2),heartbeat_median_ms=statistics.median(samples),
                    heartbeat_p95_ms=sorted(samples)[int(len(samples)*.95)],heartbeat_max_ms=max(samples),
                    detection_ms=app.detection_result.total_ms,road_ms=app.road_result.total_ms,
                    shot_events=app._shot_count,note='50ms UI heartbeat; 2s warmup excluded; one short local run, no OBS capture/encode measurement')
                out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps(data),flush=True)
                app.close();return
        app.after(50,poll)
    except Exception:app._smoke_failure()
app.after(100,poll);app.mainloop();sys.exit(1 if app.test_failed else 0)
