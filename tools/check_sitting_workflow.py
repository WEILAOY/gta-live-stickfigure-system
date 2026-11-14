from pathlib import Path
import sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1];out=base.parent/'28_坐姿检测与素材验证';out.mkdir(exist_ok=True)
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
dining='--dining' in sys.argv
if dining:source=str(base.parent/'03_测试素材/gta6_actions_test.mp4')
class App(Application):
    def _run_smoke(self):pass
app=App(base,smoke_test=True,initial_video=source,initial_position=37 if dining else 40)
app.ai_var.set(True);app.model_profile_var.set('精细');app._model_changed();app.person_action_var.set('自动姿态')
start=time.perf_counter();begun=False;seen=0;captions=set()
def poll():
    global begun,seen
    try:
        assert time.perf_counter()-start<35,(app.video_position,app.ai_status_var.get())
        if not begun:
            if app.video_frame and app.detection_result:app.start();begun=True
        else:
            # Check committed sprite layers, not merely a queued recognition result.
            for key in app.output_canvas._layer_cache:
                actor=key[0]
                if actor.kind=='person' and actor.seated and not actor.predicted:seen+=1
            if app.scene:
                presented=app._presentation_scene(app.scene)
                captions.update(e.action_caption for e in presented.entities if e.seated and e.action_caption)
            if app.video_position>=(42 if dining else 46):
                assert seen>0,'No seated preset was committed during playback'
                app.seek_video(40);assert not app.scene and not app.detection_result
                app.stop();assert app.scene is None
                (out/('sitting-dining-workflow-result.json' if dining else 'sitting-workflow-result.json')).write_text(json.dumps(dict(passed=True,seated_draw_samples=seen,captions=sorted(captions),
                    checks=[('actual dining clip 37-42s' if dining else 'actual original video 40-46s')+' playback emits seated fixed sprite layers','seek and stop clear seated state']),ensure_ascii=False,indent=2),encoding='utf-8')
                app.close();return
        app.after(40,poll)
    except Exception:app._smoke_failure()
app.after(150,poll);app.mainloop();sys.exit(1 if app.test_failed else 0)
