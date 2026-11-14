from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest,tkinter as tk
from dataclasses import replace,fields
from unittest.mock import patch
import cv2,numpy as np
from stickfigure.core import Entity,Scene,Joint
from stickfigure.rendering import SceneCanvas
from stickfigure.frame_clipping import FrameLayer,render_extent
from stickfigure.tracking import TrackManager,SceneSmoother
from stickfigure.detection import Detection
from stickfigure.assets import vehicle_drawing,preset_pose,person_pose


class PresetClippingChecks(unittest.TestCase):
    def test_only_frame_rectangle_clips_all_four_sides(self):
        layer=FrameLayer((-40,-50,240,180),(10,20,128,72))
        layer.paint('polygon',[-40,-50,240,-50,240,180,-40,180],fill='#34495e')
        data=layer.png();self.assertIsNotNone(data)
        self.assertEqual(layer.bounds,(10,20,138,92))
        self.assertTrue(layer.pixels[:,:,3].all())  # no occlusion holes

    def test_edge_material_keeps_full_size(self):
        self.assertLess(render_extent((0,200,70,400),(0,200,70,400),2)[0],0)
        self.assertGreater(render_extent((1100,200,1280,400),(1100,200,1280,400),2)[2],1280)
        self.assertLess(render_extent((400,0,600,100),(400,0,600,100),1)[1],0)
        self.assertGreater(render_extent((400,650,600,720),(400,650,600,720),1)[3],720)

    def test_partial_occlusion_preserves_known_full_extent(self):
        tracker=TrackManager()
        first=tracker.update([Detection('person',.9,(.3,.2,.5,.8),render_box=(.3,.2,.5,.8))],0)[0]
        second=tracker.update([Detection('person',.9,(.3,.2,.5,.5),render_box=(.3,.2,.5,.5))],.1)[0]
        self.assertEqual(first.track_id,second.track_id)
        self.assertAlmostEqual(second.render_box[3]-second.render_box[1],.6)
        third=tracker.update([Detection('person',.9,(.3,.2,.5,.5),render_box=(.3,.2,.5,.5))],.2)[0]
        self.assertAlmostEqual(third.render_box[3]-third.render_box[1],.6)
        self.assertAlmostEqual(third.render_box[3],.8)
        held=tracker.update([],.4)[0]
        self.assertTrue(held.predicted)
        self.assertAlmostEqual(held.render_box[3]-held.render_box[1],.6)

    def test_missing_target_retains_identity_without_painting_a_ghost(self):
        e=Entity('a','car',.5,.8,bbox=(.3,.4,.7,.8),predicted=True,missing_age=.6,sample_time=0)
        scene=Scene(0,0,1,0,(e,),False,frame_clipping=True)
        self.assertFalse(SceneSmoother().update(scene,0,1,True).entities)
        self.assertFalse(SceneSmoother().update(replace(scene,entities=(replace(e,missing_age=1.1),)),0,1,True).entities)

    def test_light_model_fill_is_transparent_so_other_complete_lines_remain(self):
        layer=FrameLayer((0,0,100,100),(0,0,100,100))
        layer.paint('polygon',[10,10,90,10,90,90,10,90],fill='#f1f5f8',outline='#34495e')
        layer.png()
        self.assertEqual(layer.pixels[50,50,3],0)
        self.assertGreater(layer.pixels[10,50,3],0)

    def test_renderer_uses_only_presets_and_has_no_pixel_or_mask_protocol(self):
        names={f.name for f in fields(Scene)}
        self.assertFalse({'visibility','strict_visibility','pixels','vehicle_edges'}&names)
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=480);canvas.pack();root.update()
        try:
            hidden=tuple(Joint(.5,.2,0) for _ in range(33))
            person=Entity('p','person',.5,.8,bbox=(.35,.15,.65,.8),pose=hidden,action='WALK')
            car=Entity('c','car',.03,.75,bbox=(0,.3,.15,.75),render_bbox=(-.3,.3,.15,.75),yaw=90)
            scene=Scene(0,0,1,.2,(person,car),False,frame_clipping=True)
            with patch('stickfigure.rendering.vehicle_drawing',wraps=vehicle_drawing) as cars,patch('stickfigure.rendering.person_pose',wraps=person_pose) as people:
                canvas.draw(scene,simulated=False)
                self.assertTrue(cars.called and people.called)
            self.assertEqual(len(canvas.find_withtag('preset-object')),2)
            self.assertTrue(all(canvas._poses['p'][0][i][2]>.9 for i in (11,12,23,24,25,26,27,28)))
            before=[p.tk.call(str(p),'data','-format','png') for p in canvas._images]
            canvas.draw(replace(scene,entities=(replace(person,pose=()),car)),simulated=False)
            after=[p.tk.call(str(p),'data','-format','png') for p in canvas._images]
            self.assertEqual(before,after)  # hidden pose pixels cannot alter material
            canvas.draw(replace(scene,entities=(replace(person,predicted=True),replace(car,predicted=True))),simulated=False)
            self.assertFalse(canvas.find_withtag('preset-object'))
            self.assertFalse(canvas.hitboxes)
            canvas.draw(scene,simulated=False)
            for _,bounds in canvas._layer_cache.values():
                self.assertGreaterEqual(bounds[0],0);self.assertGreaterEqual(bounds[1],60)
                self.assertLessEqual(bounds[2],640);self.assertLessEqual(bounds[3],420)
        finally:
            root.destroy()


if __name__=='__main__':
    unittest.main()
