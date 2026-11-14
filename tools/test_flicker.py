from pathlib import Path
import sys,tkinter as tk,unittest
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.scheduling import analysis_max_age
from stickfigure.rendering import SceneCanvas
from stickfigure.core import Scene,Entity,ShadeRegion

class FlickerChecks(unittest.TestCase):
    def test_freshness_includes_computation_and_observed_cadence_but_has_hard_cap(self):
        self.assertLess(analysis_max_age(5,80),.6)
        self.assertGreater(analysis_max_age(5,600),1)
        self.assertGreater(analysis_max_age(10,120,(0,.4,.8)),.6)
        self.assertEqual(analysis_max_age(5,9000,(0,10)),1.5)

    def test_complete_new_frame_precedes_old_frame_deletion(self):
        root=tk.Tk();c=SceneCanvas(root,width=640,height=360);c.pack();root.update()
        try:
            scene=Scene(0,0,1,0,(Entity('car','car',.5,.8,bbox=(.3,.4,.7,.8)),),frame_clipping=True,
                        shading=(ShadeRegion(0,((0,0),(1,0),(1,1),(0,1))),))
            c.draw(scene);old=set(c.find_all());old_photo=c._background_cache[1];original=c._draw
            def observe(*args):
                self.assertTrue(old.issubset(c.find_all()))
                original(*args)
                new=set(c.find_all())-old;self.assertTrue(new)
                self.assertTrue(all(c.itemcget(i,'state')=='hidden' for i in new))
                self.assertTrue(all(c.itemcget(i,'state')!='hidden' for i in old))
                self.assertIn(str(old_photo),root.tk.call('image','names'))
            with patch.object(c,'_draw',side_effect=observe):c.draw(replace(scene,entities=()))
            self.assertFalse(old.intersection(c.find_all()))
            self.assertTrue(all(c.itemcget(i,'state')=='normal' for i in c.find_all()))
            self.assertFalse(c.find_withtag('preset-object')) # negative result clears missing actor
        finally:root.destroy()

    def test_failed_render_keeps_visible_old_frame_and_images(self):
        root=tk.Tk();c=SceneCanvas(root,width=640,height=360);c.pack();root.update()
        try:
            scene=Scene(0,0,1,0,(Entity('p','person',.5,.8,bbox=(.4,.2,.6,.8)),),frame_clipping=True)
            c.draw(scene);old=c.find_all();photos=list(c._images)
            def fail(*args):c.create_rectangle(0,0,100,100,fill='white');raise ValueError('test render failure')
            with patch.object(c,'_draw',side_effect=fail):
                with self.assertRaises(ValueError):c.draw(None)
            self.assertEqual(c.find_all(),old);self.assertEqual(c._images,photos);self.assertIsNone(c._staging_tag)
            c.draw(None);self.assertFalse(c.find_withtag('preset-object'))
        finally:root.destroy()

if __name__=='__main__':unittest.main()
