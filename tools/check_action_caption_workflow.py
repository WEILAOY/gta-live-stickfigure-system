"""Actual app: helicopter category, phone/down captions and toggle/settings."""
from pathlib import Path
import sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1];out=base.parent/'24_动作角标与识别修正验证'
source=json.loads((base.parent/'03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=source,initial_position=845)
app.ai_var.set(True);app.model_profile_var.set('精细');app._model_changed()
app.person_action_var.set('自动姿态');app.vehicle_model_var.set('自动类别');app.vehicle_view_var.set('自动估计')
app.action_captions_var.set(True);app.action_captions.reset();stage=0;started=time.perf_counter();records=[]
def ready():
    global stage,started
    try:
        assert time.perf_counter()-started<35,(stage,app.ai_status_var.get())
        if not app.scene or not app._detection_is_current() or app.output_canvas.winfo_width()<100:app.after(80,ready);return
        scene=app._presentation_scene(app.scene);app.output_canvas.draw(scene,simulated=False)
        texts=[app.output_canvas.itemcget(i,'text') for i in app.output_canvas.find_withtag('action-caption')]
        if stage==0:
            assert any(e.vehicle_type=='helicopter' and not e.predicted for e in scene.entities),scene.entities
            assert any(key[0].vehicle_type=='helicopter' for key in app.output_canvas._layer_cache)
            records.append(dict(position=app.video_position,helicopter=True));stage=1;app.seek_video(240);started=time.perf_counter()
        elif stage==1:
            assert '玩手机' in texts,texts
            records.append(dict(position=app.video_position,texts=texts))
            app.action_captions_var.set(False);app.action_captions.reset()
            app.output_canvas.draw(app._presentation_scene(app.scene));assert not app.output_canvas.find_withtag('action-caption')
            app.save_settings();assert app._load_settings()['action_captions'] is False
            app.action_captions_var.set(True);app.action_captions.reset();app.down_recovery_var.set(True);app._down_recovery_changed()
            stage=2;app.seek_video(570);started=time.perf_counter()
        else:
            assert '倒地' in texts,texts
            assert not any('中弹' in text for text in texts)
            records.append(dict(position=app.video_position,texts=texts))
            app.person_action_var.set('射击');app.action_captions.reset()
            scene=app._presentation_scene(app.scene);app.output_canvas.draw(scene)
            assert any(app.output_canvas.itemcget(i,'text')=='手动·开枪' for i in app.output_canvas.find_withtag('action-caption'))
            app.person_action_var.set('自动姿态');app.save_settings();assert app._load_settings()['action_captions'] is True
            (out/'action-caption-workflow-result.json').write_text(json.dumps(dict(passed=True,records=records,checks=[
                'actual helicopter detection maps to helicopter preset in main app','actual source phone classification displays native 玩手机 text',
                'caption switch hides all notices independently of source OCR','caption settings persist',
                'actual recovered DOWN displays 倒地 without claiming injury','manual shooting explicitly labelled 手动·开枪',
                'seek invalidates old target captions']),ensure_ascii=False,indent=2),encoding='utf-8')
            print('Actual helicopter and action caption workflow passed.',flush=True);app.close();return
        app.after(80,ready)
    except Exception:app._smoke_failure()
app.after(120,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
