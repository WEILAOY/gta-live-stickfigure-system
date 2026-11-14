from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,tkinter as tk
import numpy as np
from dataclasses import replace
from stickfigure.buildings import extract_building_outlines
from stickfigure.core import Scene,BuildingGeometry,Entity
from stickfigure.rendering import SceneCanvas


class BuildingChecks(unittest.TestCase):
    def sample(self):
        labels=np.zeros((90,160),np.uint8)
        labels[12:78,25:95]=2
        return labels

    def test_only_outer_boundary_no_window_or_door_lines(self):
        labels=self.sample()
        plain=extract_building_outlines(labels)
        labels[28:40,35:44]=10
        labels[48:60,55:66]=10
        labels[40:66,76:87]=13
        holes=extract_building_outlines(labels)
        self.assertEqual(plain,holes)
        self.assertEqual(len(holes.outlines),1)
        outline=holes.outlines[0]
        self.assertEqual(outline[0],outline[-1])
        self.assertLessEqual(len(outline),9)
        self.assertTrue(any(abs(a[1]-b[1])<.05 and abs(a[0]-b[0])>.2 for a,b in zip(outline,outline[1:])))
        for x,y in outline:
            self.assertTrue(0<=x<=1 and 0<=y<=1)
            self.assertTrue(x<.2 or x>.55 or y<.18 or y>.80)

    def test_no_building_evidence_and_small_fragments_are_ignored(self):
        labels=self.sample()
        self.assertFalse(extract_building_outlines(np.zeros_like(labels)).outlines)
        self.assertFalse(extract_building_outlines(labels,np.zeros_like(labels,dtype=float)).outlines)
        fragments=np.zeros_like(labels);fragments[20:24,20:24]=2
        self.assertFalse(extract_building_outlines(fragments).outlines)

    def test_frame_border_is_not_added_as_a_building_wall(self):
        labels=np.zeros((90,160),np.uint8);labels[:70,:85]=2
        geometry=extract_building_outlines(labels)
        self.assertTrue(geometry.outlines)
        for outline in geometry.outlines:
            for a,b in zip(outline,outline[1:]):
                self.assertFalse(a[0]<.03 and b[0]<.03)
                self.assertFalse(a[1]<.03 and b[1]<.03)

    def test_city_keeps_roof_steps_and_more_than_three_distant_masses(self):
        labels=np.zeros((216,384),np.uint8)
        for x,top in ((10,25),(35,48),(60,18),(85,42),(110,30)):
            labels[top:150,x:x+25]=2
        for x in (170,210,250,290,330):
            labels[85:103,x:x+12]=2
        geometry=extract_building_outlines(labels)
        self.assertEqual(len(geometry.outlines),6)
        roof=[p for p in geometry.outlines[0] if p[1]<.3]
        self.assertGreaterEqual(len(roof),8)
        self.assertGreaterEqual(len({round(y,2) for x,y in roof}),4)

    def test_renderer_has_outer_polylines_only_and_clears_them(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            buildings=BuildingGeometry((((.1,.7),(.1,.2),(.3,.2),(.3,.7)),))
            car=Entity('car','car',.5,.8,bbox=(.3,.4,.7,.8))
            scene=Scene(0,0,1,0,(car,),False,frame_clipping=True,buildings=buildings)
            canvas.draw(scene,simulated=False)
            items=canvas.find_withtag('building-outline')
            self.assertEqual(len(items),1)
            self.assertEqual(canvas.type(items[0]),'line')
            self.assertEqual(len(canvas.coords(items[0])),8)
            self.assertTrue(canvas.find_withtag('preset-object'))
            canvas.draw(replace(scene,buildings=None),simulated=False)
            self.assertFalse(canvas.find_withtag('building-outline'))
            self.assertTrue(canvas.find_withtag('preset-object'))
        finally:
            root.destroy()


if __name__=='__main__':
    unittest.main()
