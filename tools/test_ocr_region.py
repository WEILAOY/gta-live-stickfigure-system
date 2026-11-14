from pathlib import Path
import sys,unittest,threading,tempfile,json
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.ocr import TextRecognizer,TextWorker,normalize_roi
from stickfigure.ocr_region import canvas_roi
from stickfigure.video import VideoFrame
from stickfigure.app import Application

class RegionChecks(unittest.TestCase):
    def test_drag_reverse_clamp_and_tiny_rejection(self):
        self.assertEqual(canvas_roi((180,90),(20,30),(0,0,200,100)),(.1,.3,.9,.9))
        self.assertEqual(canvas_roi((-20,-20),(230,150),(10,10,200,100)),(0,0,1,1))
        for roi in ((0,0,0,1),(0,0,float('nan'),1),(-1,0,1,1)):
            with self.assertRaises(ValueError):normalize_roi(roi)
        with self.assertRaises(ValueError):canvas_roi((2,2),(3,3),(0,0,200,100))
    def test_crop_precedes_engine_and_boxes_return_to_full_frame(self):
        recognizer=TextRecognizer.__new__(TextRecognizer);sizes=[]
        def engine(image):
            sizes.append(image.shape)
            return SimpleNamespace(boxes=[[[0,0],[40,0],[40,20],[0,20]]],txts=['字幕'],scores=[.99])
        recognizer.engine=engine
        frame=VideoFrame(1,0,200,100,np.zeros((100,200,3),np.uint8).tobytes())
        regions,_=recognizer.recognize(frame,(.2,.6,.6,1),1.)
        self.assertEqual(sizes,[(40,80,3)])
        self.assertEqual(regions[0].box,(.2,.6,.4,.8))
    def test_unchanged_pixels_reuse_but_generation_and_changed_pixels_rerun(self):
        calls=[]
        class Fake:
            def __init__(self,*args):pass
            def recognize(self,frame):calls.append(frame.timestamp);return (),5
        with patch('stickfigure.ocr.TextRecognizer',Fake):
            w=TextWorker('unused')
            try:
                w.submit(VideoFrame(1,0,1,1,b'\0\0\0'));self.assertFalse(w.results.get(timeout=2).reused)
                w.submit(VideoFrame(1,1,1,1,b'\0\0\0'));self.assertTrue(w.results.get(timeout=2).reused)
                w.submit(VideoFrame(1,2,1,1,b'\1\0\0'));self.assertFalse(w.results.get(timeout=2).reused)
                w.submit(VideoFrame(2,3,1,1,b'\1\0\0'));self.assertFalse(w.results.get(timeout=2).reused)
                self.assertEqual(calls,[0,2,3])
            finally:w.close();w._thread.join(2)
    def test_range_change_discards_inflight_result(self):
        entered=threading.Event();release=threading.Event()
        class Fake:
            def __init__(self,*args):pass
            def recognize(self,frame,*args):
                if not args:entered.set();release.wait(2)
                return (),1
        with patch('stickfigure.ocr.TextRecognizer',Fake):
            w=TextWorker('unused')
            try:
                frame=VideoFrame(1,0,2,2,b'\0'*12);w.submit(frame);self.assertTrue(entered.wait(1))
                w.configure((0,.5,1,1),1.);w.submit(frame);release.set()
                result=w.results.get(timeout=2);self.assertEqual(result.epoch,w.epoch)
                self.assertTrue(w.results.empty())
            finally:release.set();w.close();w._thread.join(2)
    def test_settings_keep_normalized_range_quality_and_fractional_rate(self):
        class App(Application):
            def _run_smoke(self):pass
        app=App(Path(__file__).resolve().parents[1],smoke_test=True)
        try:
            with tempfile.TemporaryDirectory() as folder:
                app.settings_path=Path(folder)/'settings.json'
                app.text_rate_var.set('.5');app._apply_text_region((.1,.7,.9,.95),1.)
                settings=app._load_settings()
                self.assertEqual(settings['text_roi'],(.1,.7,.9,.95))
                self.assertEqual(settings['text_scale'],1.);self.assertEqual(settings['text_rate'],.5)
                app._apply_text_region(None,1.5);self.assertIsNone(app._load_settings()['text_roi'])
        finally:
            for ident in app.tk.call('after','info'):app.after_cancel(ident)
            app.close()

if __name__=='__main__':unittest.main()
