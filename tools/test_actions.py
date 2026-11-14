from pathlib import Path
import sys,math,unittest,tkinter as tk
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.assets import ACTIONS,ACTION_GROUPS,ANIMATED_ACTIONS,preset_pose,person_props,BODY_LINKS
from stickfigure.actions import classify_action,action_mirror,ActionStabilizer
from stickfigure.detection import Detection,ObjectHint,attach_object_hints
from stickfigure.core import Entity,Scene
from stickfigure.rendering import SceneCanvas
from stickfigure.vision import PoseEstimator
import numpy as np


class ActionChecks(unittest.TestCase):
    def test_upper_body_can_select_phone_without_visible_hips_or_legs(self):
        pose=list(preset_pose('PHONE'))
        for i in range(23,33):pose[i]=replace(pose[i],confidence=0)
        self.assertEqual(classify_action(pose),'HAND_FACE')
        self.assertEqual(classify_action(pose,object_hints=(self.hint('phone',pose),)),'PHONE')

    def test_portrait_roi_extends_only_when_feet_are_not_supported(self):
        estimator=object.__new__(PoseEstimator)
        pose=list(preset_pose('IDLE'))
        for i in (27,28):pose[i]=replace(pose[i],confidence=0)
        with patch.object(estimator,'_estimate_roi',side_effect=[tuple(pose),preset_pose('PHONE')]) as infer:
            estimator.estimate(np.zeros((480,852,3),np.uint8),(.1,.1,.8,1))
            self.assertEqual(infer.call_count,2)
            self.assertGreater(infer.call_args.args[1][3],1)
        with patch.object(estimator,'_estimate_roi',return_value=preset_pose('IDLE')) as infer:
            estimator.estimate(np.zeros((480,852,3),np.uint8),(.1,.1,.8,1))
            self.assertEqual(infer.call_count,1)

    def test_catalog_has_complete_finite_presets_and_bounded_props(self):
        grouped=[name for group in ACTION_GROUPS.values() for name in group]
        self.assertEqual(set(grouped),set(ACTIONS)-{'自动姿态'})
        self.assertEqual(len(grouped),26)
        for action in ACTIONS.values():
            if action is None:continue
            for t in (0,.13,.6,1.2,1.8):
                pose=preset_pose(action,t)
                self.assertEqual(len(pose),33)
                for a,b in BODY_LINKS:
                    self.assertEqual((pose[a].confidence,pose[b].confidence),(1,1))
                for p in pose:
                    self.assertTrue(math.isfinite(p.x+p.y))
                    if p.confidence:self.assertTrue(0<=p.x<=1 and 0<=p.y<=1,(action,t,p))
                for prop in person_props(action,t):
                    self.assertTrue(all(0<=v<=1 for v in prop.points),(action,t,prop))

    def test_dynamic_actions_change_and_mirroring_only_reflects_fixed_material(self):
        for action in ANIMATED_ACTIONS:
            self.assertNotEqual(preset_pose(action,0),preset_pose(action,.17),action)
        a,b=preset_pose('POINT',.2),preset_pose('POINT',.2,True)
        for p,q in zip(a,b):
            if p.confidence:self.assertAlmostEqual(p.x,1-q.x);self.assertEqual(p.y,q.y)
        self.assertFalse(action_mirror(a,'POINT'))
        self.assertTrue(action_mirror(b,'POINT'))

    def test_new_coarse_pose_categories(self):
        for action in ('WAVE','POINT','GESTURE','HAND_FACE','ARMS_FORWARD','SIT_GESTURE'):
            self.assertEqual(classify_action(preset_pose(action,0)),action)

    def hint(self,label,pose):
        p=pose[16]
        return ObjectHint(label,.8,(p.x-.015,p.y-.015,p.x+.015,p.y+.015))

    def test_phone_and_drink_require_nearby_object_evidence(self):
        phone=preset_pose('PHONE');look=preset_pose('PHONE_LOOK');drink=preset_pose('DRINK',1/(.28*2))
        self.assertEqual(classify_action(phone),'HAND_FACE')
        self.assertEqual(classify_action(phone,object_hints=(self.hint('phone',phone),)),'PHONE')
        self.assertNotEqual(classify_action(look),'PHONE_LOOK')
        self.assertEqual(classify_action(look,object_hints=(self.hint('phone',look),)),'PHONE_LOOK')
        self.assertNotEqual(classify_action(drink),'DRINK')
        self.assertEqual(classify_action(drink,object_hints=(self.hint('cup',drink),)),'DRINK')
        distant=ObjectHint('phone',.9,(.01,.8,.03,.9))
        self.assertEqual(classify_action(phone,object_hints=(distant,)),'HAND_FACE')

    def test_props_remain_context_and_do_not_become_drawable_targets(self):
        people=(Detection('person',.9,(.1,.1,.4,.9)),Detection('person',.9,(.6,.1,.9,.9)))
        hint=ObjectHint('phone',.8,(.2,.2,.25,.3))
        out=attach_object_hints(people,(hint,))
        self.assertEqual(len(out),2)
        self.assertEqual(out[0].object_hints,(hint,));self.assertFalse(out[1].object_hints)
        self.assertTrue(all(d.label=='person' for d in out))

    def test_action_filter_rejects_flicker_accepts_sustained_change_and_resets_on_seek(self):
        s=ActionStabilizer()
        self.assertEqual(s.update('IDLE',False,0),('IDLE',False))
        self.assertEqual(s.update('POINT',False,.1),('IDLE',False))
        self.assertEqual(s.update('IDLE',False,.2),('IDLE',False))
        s.update('POINT',True,.3);s.update('POINT',True,.4)
        self.assertEqual(s.update('POINT',True,.5),('POINT',True))
        self.assertEqual(s.update('UNKNOWN',False,.6),('POINT',True))
        self.assertEqual(s.update('UNKNOWN',False,.9),('IDLE',False))
        self.assertEqual(s.update('UNKNOWN',False,0),('IDLE',False))

    def test_new_animation_invalidates_cache_and_props_use_preset_renderer(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            person=Entity('one','person',.5,.9,bbox=(.25,.1,.75,.9),action='WAVE')
            scene=Scene(1,0,1,0,(person,),False,frame_clipping=True)
            canvas.draw(scene,simulated=False)
            before=canvas._images[0].tk.call(str(canvas._images[0]),'data','-format','png')
            canvas.draw(replace(scene,animation_time=.2),simulated=False)
            after=canvas._images[0].tk.call(str(canvas._images[0]),'data','-format','png')
            self.assertNotEqual(before,after)
            canvas.draw(replace(scene,frame_clipping=False,entities=(replace(person,action='LIFT'),)),simulated=False)
            self.assertTrue(canvas.find_withtag('preset-prop'))
        finally:root.destroy()

if __name__=='__main__':unittest.main()
