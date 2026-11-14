"""Real UI/model-switch playback check for the local DirectML driver."""
from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application

base=Path(__file__).resolve().parents[1]
app=Application(base,initial_video=str(base.parent/'03_测试素材/gta5_test_01.mp4'),initial_position=90)
app.ai_var.set(True);app.road_var.set(True);app.buildings_var.set(True)
app.detect_rate_var.set('15');app.road_rate_var.set('5');app.fps_var.set('30')
app._detection_changed();app._road_changed()
steps=[('精细',90),('快速',35),('均衡',90),('精细',30),('精细',90)]
records=[];started=time.perf_counter()

def step(index):
    try:
        if index==len(steps):
            assert all(r['detections'] and r['buildings'] for r in records)
            report=dict(passed=True,duration_seconds=time.perf_counter()-started,steps=records,
                        note='Short actual playback with model reloads, seeks, both GPU workers and complete shutdown; not a long-term stability guarantee.')
            (base.parent/'12_城市群与识别对照/gpu-switch-stress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            app.close();return
        profile,position=steps[index]
        app.pause()
        app.model_profile_var.set(profile);app._model_changed()
        app.seek_video(position);app.start()
        app.after(3500,lambda:check(index))
    except Exception:app._smoke_failure()

def check(index):
    try:
        assert app.ai_var.get(),app.ai_status_var.get()
        assert app.detection_result and app.road_result
        assert app.detection_result.epoch==app.detector.epoch
        assert app.detection_result.generation==app.video.generation
        assert app.detection_result.backend.startswith('GPU')
        assert app.road_result.backend.startswith('GPU')
        records.append(dict(profile=steps[index][0],position=app.video_position,
                            detections=len([d for d in app.detection_result.detections if d.confirmed and not d.predicted]),
                            buildings=len(app.road_result.buildings.outlines),
                            human_ms=app.detection_result.total_ms,environment_ms=app.road_result.total_ms))
        step(index+1)
    except Exception:app._smoke_failure()

app.after(1500,lambda:step(0))
app.mainloop()
sys.exit(1 if app.test_failed else 0)
