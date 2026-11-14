from pathlib import Path
import sys,unittest,threading,queue,tkinter as tk
from unittest.mock import patch
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.ocr import clean_regions,TextWorker,text_free_outlines
from stickfigure.core import TextRegion,Scene,Entity
from stickfigure.video import VideoFrame
from stickfigure.rendering import SceneCanvas

class OcrChecks(unittest.TestCase):
    def test_small_letter_fragments_are_not_drawn_as_buildings_but_real_facade_survives(self):
        letter=((.44,.33),(.59,.33),(.59,.55),(.44,.55))
        star=((.46,.60),(.54,.60),(.54,.65),(.46,.65))
        facade=((0,0),(1,0),(1,1),(0,1))
        remote=((.1,.1),(.2,.1),(.2,.2),(.1,.2))
        text=TextRegion('R',.99,(.46,.42,.55,.58))
        self.assertEqual(text_free_outlines((letter,star,facade,remote),(text,)),(facade,remote))
        self.assertEqual(text_free_outlines((letter,),()),(letter,))

    def test_unicode_confidence_dedup_and_frame_bounds(self):
        q=[[-10,10],[100,10],[100,40],[-10,40]]
        result=clean_regions([q,q,q,q],['中文 GTA6\x00','中文 GTA6','garbage',''],[.9,.8,.2,.9],200,100)
        self.assertEqual(len(result),1);self.assertEqual(result[0].text,'中文 GTA6')
        self.assertEqual(result[0].box,(0,.1,.5,.4))
        self.assertFalse(clean_regions([],[],[],200,100))

    def test_rendered_content_is_native_text_and_empty_result_clears_it(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            region=TextRegion('中文字幕 GTA6 123',.95,(.2,.8,.8,.9))
            scene=Scene(1,0,1,0,(),False,frame_clipping=True,texts=(region,))
            canvas.draw(scene,simulated=False)
            items=canvas.find_withtag('ocr-text');self.assertEqual(len(items),1)
            self.assertEqual(canvas.type(items[0]),'text')
            self.assertEqual(canvas.itemcget(items[0],'text'),region.text)
            x1,y1,x2,y2=canvas.bbox(items[0]);self.assertTrue(120<=x1<x2<=515 and 280<=y1<y2<=330)
            canvas.draw(replace(scene,texts=()),simulated=False)
            self.assertFalse(canvas.find_withtag('ocr-text'))
            canvas.draw(scene,simulated=False,gallery=True)
            self.assertFalse(canvas.find_withtag('ocr-text'))
        finally:root.destroy()

    def test_reset_drops_inflight_and_worker_processes_latest_frame(self):
        entered,release=threading.Event(),threading.Event();calls=[]
        class Fake:
            def __init__(self,*args):pass
            def recognize(self,frame):
                calls.append(frame.timestamp)
                if len(calls)==1:entered.set();assert release.wait(3)
                return (TextRegion(str(frame.timestamp),.9,(.1,.1,.5,.2)),),1
        with patch('stickfigure.ocr.TextRecognizer',Fake):
            w=TextWorker('unused')
            try:
                w.submit(VideoFrame(1,0,1,1,b'\0\0\0'));self.assertTrue(entered.wait(2));w.reset()
                for t in range(1,6):w.submit(VideoFrame(2,t,1,1,b'\0\0\0'))
                release.set();r=w.results.get(timeout=3)
                self.assertEqual((r.epoch,r.generation,r.timestamp),(w.epoch,2,5));self.assertEqual(calls,[0,5])
                with self.assertRaises(queue.Empty):w.results.get(timeout=.1)
            finally:release.set();w.close();w._thread.join(3)

    def test_missing_weights_report_failure_without_text(self):
        w=TextWorker(Path(__file__).parent/'missing-ocr')
        try:
            w.submit(VideoFrame(1,0,1,1,b'\0\0\0'))
            epoch,message=w.events.get(timeout=10)
            self.assertTrue(message);self.assertEqual(epoch,w.epoch);self.assertTrue(w.results.empty())
        finally:w.close();w._thread.join(3)

if __name__=='__main__':unittest.main()
