from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.actions import seated_evidence,seated_posture,seated_mirror,classify_action,seat_context_evidence
from stickfigure.assets import preset_pose,person_pose
from stickfigure.core import Entity,Scene
from stickfigure.rendering import SceneCanvas
from stickfigure.captions import ActionCaptions
from stickfigure.detection import ObjectHint,Detection,attach_object_hints

class SittingChecks(unittest.TestCase):
    def test_seat_context_requires_independent_seat_and_lower_body_overlap(self):
        person=Detection('person',.9,(.2,.2,.5,.8))
        chair=ObjectHint('chair',.9,(.18,.5,.35,.8))
        attached=attach_object_hints((person,),(chair,))[0]
        self.assertTrue(seat_context_evidence(attached,1.77))
        self.assertFalse(seat_context_evidence(person,1.77))
        self.assertFalse(seat_context_evidence(replace(attached,object_hints=(replace(chair,confidence=.4),)),1.77))
    def test_standing_or_remote_chair_is_not_seated(self):
        person=Detection('person',.9,(.2,.1,.35,.9))
        chair=ObjectHint('chair',.9,(.2,.5,.4,.9))
        self.assertFalse(seat_context_evidence(replace(person,object_hints=(chair,)),1.77))
        wide=replace(person,box=(.2,.2,.5,.8))
        remote=replace(chair,box=(.8,.6,.9,.9))
        self.assertFalse(seat_context_evidence(replace(wide,object_hints=(remote,)),1.77))
    def test_sitting_both_directions_and_other_actions_rejected(self):
        for mirror in (False,True):
            p=preset_pose('SIT',mirror=mirror)
            self.assertTrue(seated_posture(p));self.assertEqual(seated_mirror(p),mirror)
            self.assertEqual(classify_action(p),'SIT')
        for action in ('IDLE','CROUCH','WALK','RUN','DOWN','CLIMB'):
            for t in (0,.13,.3,.6):self.assertFalse(seated_posture(preset_pose(action,t)),(action,t))
    def test_upper_body_only_is_not_seated_and_weak_single_leg_is_unknown(self):
        p=list(preset_pose('SIT'))
        for i in (25,26,27,28):p[i]=replace(p[i],confidence=0)
        self.assertIsNone(seated_evidence(p))
        p=list(preset_pose('SIT'));p[27]=replace(p[27],confidence=.3);p[28]=replace(p[28],confidence=0)
        self.assertIsNone(seated_evidence(p))
    def test_sitting_phone_preserves_semantic_action_and_fixed_legs(self):
        p=person_pose('PHONE_LOOK',.2,seated=True,seat_mirror=True)
        self.assertTrue(seated_posture(p))
        hand=p[16];hint=ObjectHint('phone',.95,(hand.x-.02,hand.y-.02,hand.x+.02,hand.y+.02))
        self.assertEqual(classify_action(p,object_hints=(hint,)),'PHONE_LOOK')
        self.assertEqual(p[25:33],preset_pose('SIT',mirror=True)[25:33])
        self.assertEqual(p[:23],preset_pose('PHONE_LOOK',.2)[:23])
    def test_seated_gesture_outranks_generic_arm_gesture(self):
        self.assertEqual(classify_action(preset_pose('SIT_GESTURE')),'SIT_GESTURE')
        p=list(preset_pose('RAISE'));lower=preset_pose('SIT')
        p[23:33]=lower[23:33]
        self.assertEqual(classify_action(p),'SIT_GESTURE')
    def test_rendering_uses_composed_presets_and_caption_expires(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            actor=Entity('s','person',.5,.9,bbox=(.25,.1,.75,.9),action='PHONE_LOOK',seated=True,seat_mirror=True)
            scene=Scene(1,0,1,0,(actor,),False,frame_clipping=True)
            with patch('stickfigure.rendering.person_pose',wraps=person_pose) as fixed:
                canvas.draw(scene,simulated=False);self.assertTrue(fixed.call_args.args[3])
            self.assertTrue(canvas.find_withtag('preset-object'))
            self.assertLess(max(canvas._poses['s'][0][i][1] for i in (27,28)),720)
            captions=ActionCaptions();self.assertEqual(captions.apply(scene).entities[0].action_caption,'坐姿·玩手机')
            self.assertFalse(captions.apply(replace(scene,animation_time=2.1)).entities[0].action_caption)
        finally:root.destroy()
    def test_seated_metadata_does_not_make_predicted_person_visible(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            actor=Entity('s','person',.5,.9,bbox=(.25,.1,.75,.9),action='SIT',seated=True,predicted=True)
            canvas.draw(Scene(1,0,1,0,(actor,),False,frame_clipping=True),simulated=False)
            self.assertFalse(canvas.find_withtag('preset-object'))
        finally:root.destroy()

if __name__=='__main__':unittest.main()
