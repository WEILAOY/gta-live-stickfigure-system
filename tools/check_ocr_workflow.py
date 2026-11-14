"""Real OCR, text-only output, seek, disable, expiry and persistence checks."""
from pathlib import Path
import sys,time,json
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
base=Path(__file__).resolve().parents[1];out=base.parent/'14_OCR文字验证';out.mkdir(exist_ok=True)
class TestApp(Application):
    def _run_smoke(self):pass
app=TestApp(base,smoke_test=True,initial_video=str(base.parent/'03_测试素材/gta6_actions_test.mp4'),initial_position=95)
app.text_var.set(True);app.text_rate_var.set('1');app.text_roi=None;app.text_scale=1.5;app._text_changed()
started=time.perf_counter();records={}
def ready():
    try:
        if not app._text_is_current():
            assert time.perf_counter()-started<30,app.text_status_var.get()
            app.after(100,ready);return
        assert app.text_result.regions
        assert not app.ai_var.get() and not app.road_var.get()
        scene=app._presentation_scene(None);assert scene and scene.texts and not scene.entities
        app.output_canvas.draw(scene,simulated=False)
        items=app.output_canvas.find_withtag('ocr-text');assert items
        records['recognized']=[app.output_canvas.itemcget(i,'text') for i in items]
        assert all(app.output_canvas.type(i)=='text' for i in items)
        r=app.text_result;app.text_result=replace(r,timestamp=r.timestamp-5)
        assert not app._text_is_current();app.text_result=r
        app.text_var.set(False);app._text_changed();app.output_canvas.draw(app._presentation_scene(None),simulated=False)
        assert not app.output_canvas.find_withtag('ocr-text')
        app.text_var.set(True);app._text_changed();app.seek_video(50)
        assert app.text_result is None
        app._ocr_test_started=time.perf_counter();app.after(100,seeked)
    except Exception:app._smoke_failure()
def seeked():
    try:
        if not app._text_is_current():
            assert time.perf_counter()-app._ocr_test_started<20
            app.after(100,seeked);return
        assert app.text_result.generation==app.video.generation
        assert any('EFFLU' in r.text.upper() for r in app.text_result.regions),[r.text for r in app.text_result.regions]
        records['english_ocr']=[r.text for r in app.text_result.regions]
        app.save_settings();assert app._load_settings()['text_enabled']
        app.start();app.after(3500,playing)
    except Exception:app._smoke_failure()
def playing():
    try:
        assert app.text_result and app.text_result.timestamp>50.5
        records['latest_ms']=app.text_result.total_ms
        app.ai_var.set(True);app._detection_changed();app.road_var.set(True);app.buildings_var.set(True);app._road_changed()
        app._ocr_test_started=time.perf_counter();app.after(200,combined)
    except Exception:app._smoke_failure()
def combined():
    try:
        if not (app.scene and app.scene.entities and app._text_is_current() and app.text_result.regions and app.road_result):
            assert time.perf_counter()-app._ocr_test_started<20
            app.after(200,combined);return
        app.output_canvas.draw(app._presentation_scene(app.scene),simulated=False)
        assert app.output_canvas.find_withtag('preset-object') and app.output_canvas.find_withtag('ocr-text')
        app.stop();assert app.text_result is None and app._presentation_scene(None) is None
        report=dict(passed=True,records=records,checks=['actual Chinese subtitle OCR','native text canvas items','text-only output without actors or environment',
          'stale text expires','disable clears text','seek invalidates old text','new generation re-recognized','English sign OCR',
          'settings roundtrip','real playback refreshes OCR','text and preset actors coexist with environment analysis','stop clears output'])
        (out/'ocr-workflow-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');app.close()
    except Exception:app._smoke_failure()
app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
