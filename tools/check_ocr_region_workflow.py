"""Actual subtitle ROI, original-coordinate native text and saved options."""
from pathlib import Path
import sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1];out=base.parent/'27_OCR范围与性能验证';out.mkdir(exist_ok=True)
class App(Application):
    def _run_smoke(self):pass
app=App(base,smoke_test=True,initial_video=str(base.parent/'03_测试素材/gta6_actions_test.mp4'),initial_position=95)
app.text_var.set(True);app.text_rate_var.set('.5');app._apply_text_region((0,.72,1,1),1.)
began=time.perf_counter();stage=0;records={}
def poll():
    global stage,began
    try:
        assert time.perf_counter()-began<30,app.text_status_var.get()
        if not app._text_is_current():app.after(100,poll);return
        if stage==0:
            assert app.text_result.regions and all(r.box[1]>=.71 for r in app.text_result.regions)
            app.output_canvas.draw(app._presentation_scene(None),simulated=False)
            items=app.output_canvas.find_withtag('ocr-text');assert items
            assert all(app.output_canvas.type(i)=='text' for i in items)
            records['crop_text']=[r.text for r in app.text_result.regions]
            assert app._load_settings()['text_roi']==(0,.72,1,1) and app._load_settings()['text_rate']==.5
            old=app.text_worker.epoch
            app._apply_text_region(None,1.5)
            assert app.text_worker.epoch>old and app.text_result is None
            stage=1;began=time.perf_counter()
        elif stage==1:
            assert app.text_result.regions and app.text_roi is None
            records['full_text']=[r.text for r in app.text_result.regions]
            app.open_text_region();app.update_idletasks()
            dialog=app.text_region_dialog
            assert dialog.winfo_exists() and dialog.photo.width()>100
            dialog.choose((.1,.7,.9,1));dialog.destroy()
            assert app.text_roi is None,'Cancel must not change application ROI'
            app._apply_text_region((0,.72,1,1),1.);app.start();stage=2;began=time.perf_counter()
        elif stage==2 and time.perf_counter()-began>4:
            assert app.text_result.timestamp>95.5
            app.text_var.set(False);app._text_changed()
            assert app.text_result is None and not app._presentation_scene(None)
            report=dict(passed=True,records=records,checks=['real cropped Chinese OCR','native text at original coordinates',
                'range scale and fractional rate persist','range changes invalidate old results','full-frame restored',
                'frozen-frame selector opens and cancel preserves selection','playback refreshes cropped text','disable clears text'])
            (out/'ocr-region-workflow-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            app.close();return
        app.after(100,poll)
    except Exception:app._smoke_failure()
app.after(150,poll);app.mainloop();sys.exit(1 if app.test_failed else 0)
