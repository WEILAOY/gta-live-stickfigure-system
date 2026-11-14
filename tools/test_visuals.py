"""Behavior checks for changing horizon, blank rendering and visual controls."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import tkinter as tk
import cv2
import numpy as np
from stickfigure.assets import vehicle_drawing,preset_pose
from stickfigure.vision import HorizonEstimator,classify_action
from stickfigure.core import Scene,Horizon,Entity
from stickfigure.rendering import SceneCanvas


class VisualChecks(unittest.TestCase):
    def perspective(self,y):
        image=np.full((315,560,3),110,dtype=np.uint8)
        for x in (0,50,110,450,510,559):
            cv2.line(image,(280,y),(x,314),(225,225,225),3)
        return image

    def test_horizon_moves_with_evidence_and_holds_on_blank_frame(self):
        estimator=HorizonEstimator()
        first=estimator.estimate(self.perspective(80))
        self.assertGreater(first.confidence,.3)
        for _ in range(8):
            second=estimator.estimate(self.perspective(145))
        self.assertGreater((second.left+second.right)/2,(first.left+first.right)/2+.08)
        blank=estimator.estimate(np.full((315,560,3),90,dtype=np.uint8))
        self.assertEqual((second.left,second.right),(blank.left,blank.right))
        self.assertLess(blank.confidence,second.confidence)
        self.assertEqual(HorizonEstimator().estimate(np.full((315,560,3),90,dtype=np.uint8)).confidence,0)

    def test_car_has_distinct_eight_views_and_top_view(self):
        drawings=[vehicle_drawing(yaw,22) for yaw in range(0,360,45)]
        signatures={str(drawing.shapes) for drawing in drawings}
        self.assertEqual(len(signatures),8)
        self.assertNotEqual(vehicle_drawing(0,22),vehicle_drawing(0,78))
        for drawing in drawings+[vehicle_drawing(123,57)]:
            self.assertGreater(drawing.aspect,0)
            self.assertTrue(all(-1e-6<=value<=1.000001 for primitive in drawing.shapes for value in primitive.points))

    def test_basic_pose_states_and_time_varying_walk(self):
        for action in ("IDLE","RAISE","CROUCH","SIT"):
            self.assertEqual(classify_action(preset_pose(action)),action)
        self.assertNotEqual(preset_pose("WALK",0),preset_pose("WALK",.2))
        self.assertNotEqual(preset_pose("RUN",.1),preset_pose("WALK",.1))

    def test_clean_canvas_has_only_horizon_without_entities(self):
        root=tk.Tk()
        canvas=SceneCanvas(root,width=640,height=360)
        canvas.pack();root.update()
        try:
            scene=Scene(1,0,1,0,(),False,horizon=Horizon(.30,.36,.8,"test"))
            canvas.draw(scene,debug=False,simulated=False)
            self.assertEqual(len(canvas.find_all()),1)
            self.assertEqual(canvas.gettags(canvas.find_all()[0]),("horizon",))
            coords=canvas.coords(canvas.find_all()[0])
            self.assertNotEqual(coords[1],coords[3])
            canvas.draw(Scene(1,0,1,0,(Entity("car","car",.5,.8,bbox=(.2,.3,.8,.8),yaw=135),),False),simulated=False)
            self.assertTrue(canvas.find_withtag("vehicle"))
            self.assertFalse(canvas.find_withtag("road"))
            self.assertFalse(canvas.find_withtag("building"))
        finally:
            root.destroy()


if __name__=="__main__":
    unittest.main()
