from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,tkinter as tk
import numpy as np
from stickfigure.curbs import extract_curbs,driving_view
from stickfigure.scheduling import FrameCadence
from stickfigure.core import RoadGeometry,Scene
from stickfigure.rendering import SceneCanvas


class CurbChecks(unittest.TestCase):
    def example(self,vehicle=False):
        labels=np.ones((90,160),np.uint8)
        for y in range(28,90):
            fraction=(y-28)/62
            a,b=int(68-58*fraction),int(92+58*fraction)
            labels[y,a:b]=0
        if vehicle:
            labels[52:75,65:95]=13
        probability=np.where(labels==0,.9,.05).astype(np.float32)
        rgb=np.full((315,560,3),110,np.uint8)
        return labels,probability,rgb

    def test_car_hole_does_not_become_curb(self):
        normal=extract_curbs(*self.example(False))
        occluded=extract_curbs(*self.example(True))
        self.assertTrue(all(normal) and all(occluded))
        for a,b in zip(normal,occluded):
            self.assertLess(max(abs(x[0]-y[0]) for x,y in zip(a,b)),.04)
        self.assertTrue(all(x<.5 for x,y in occluded[0]))
        self.assertTrue(all(x>.5 for x,y in occluded[1]))

    def test_frame_border_and_no_evidence_do_not_create_edges(self):
        labels=np.zeros((90,160),np.uint8)
        rgb=np.full((315,560,3),110,np.uint8)
        self.assertEqual(extract_curbs(labels,np.ones((90,160),np.float32),rgb),((),()))
        a,p,image=self.example()
        self.assertEqual(extract_curbs(a,np.zeros_like(p),image),((),()))

    def test_driving_view_prior_has_manual_mode_use_case(self):
        labels,_,_=self.example(True)
        self.assertTrue(driving_view(labels))
        labels[40:89,40:60]=11
        self.assertFalse(driving_view(labels))

    def test_renderer_uses_two_open_lines_never_closed_polygons(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360)
        canvas.pack();root.update()
        try:
            road=RoadGeometry(left_edge=((.4,.4),(.1,.9)),right_edge=((.6,.4),(.9,.9)),driving_view=True)
            canvas.draw(Scene(0,0,1,0,(),False,road=road),simulated=False)
            items=canvas.find_withtag('road-boundary')
            self.assertEqual(len(items),2)
            self.assertTrue(all(canvas.type(item)=='line' for item in items))
            for item in items:
                coords=canvas.coords(item)
                self.assertNotEqual(coords[:2],coords[-2:])
            legacy=RoadGeometry(polygons=(((0,.5),(1,.5),(1,1),(0,1)),))
            canvas.draw(Scene(0,0,1,0,(),False,road=legacy),simulated=False)
            self.assertFalse(canvas.find_withtag('road-boundary'))
        finally:
            root.destroy()


class CadenceChecks(unittest.TestCase):
    def test_ten_hz_on_24fps_is_not_rounded_down_to_eight(self):
        cadence=FrameCadence()
        accepted=[i/24 for i in range(240) if cadence.ready(i/24,10)]
        self.assertEqual(len(accepted),100)
        self.assertGreater(min(b-a for a,b in zip(accepted,accepted[1:])),1/24)
        self.assertLess(max(b-a for a,b in zip(accepted,accepted[1:])),.126)

    def test_pause_duplicate_rate_change_and_seek(self):
        cadence=FrameCadence()
        self.assertTrue(cadence.ready(5,5))
        self.assertFalse(cadence.ready(5,5))
        self.assertTrue(cadence.ready(5.05,10))
        self.assertTrue(cadence.ready(0,10))
        self.assertFalse(cadence.ready(0,10))


if __name__=='__main__':
    unittest.main()
