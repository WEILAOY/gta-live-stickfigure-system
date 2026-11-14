"""Contact marks follow current fixed-rig support, without retained poses."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
import unittest
from stickfigure.assets import bind_pose,person_pose
from stickfigure.core import Entity,Joint
from stickfigure.shading import contact_shadow_boxes


BOX=(400.,100.,552.,500.)


def bound_actor(action='IDLE'):
    pose=tuple(Joint((BOX[0]+p.x*(BOX[2]-BOX[0]))/1280,
                     (BOX[1]+p.y*(BOX[3]-BOX[1]))/720,p.confidence)
               for p in person_pose(action,0))
    actor=Entity('person','person',476/1280,500/720,action=action,pose=pose,
                 bbox=tuple(v/(1280 if i%2==0 else 720) for i,v in enumerate(BOX)),
                 seated=action=='SIT')
    return actor,bind_pose(pose,BOX,action,seated=actor.seated)


class BoundShadowChecks(unittest.TestCase):
    def test_crouch_and_sitting_contact_follows_final_feet(self):
        for action in ('CROUCH','SIT'):
            with self.subTest(action=action):
                actor,bound=bound_actor(action)
                self.assertIsNotNone(bound)
                old=contact_shadow_boxes((actor,))[0]
                current=contact_shadow_boxes((actor,),{actor.track_id:bound})[0]
                feet=[bound.joints[i] for i in (27,28,31,32)]
                ground=max(p.y for p in feet);height=bound.frame[3]-bound.frame[1]
                self.assertAlmostEqual(current[1]*720,ground-height*.025)
                self.assertAlmostEqual(current[3]*720,ground+height*.015)
                self.assertAlmostEqual((current[0]+current[2])*1280/2,
                                       (min(p.x for p in feet)+max(p.x for p in feet))/2)
                self.assertGreater(abs(current[1]-old[1])*720,20)

    def test_horizontal_support_uses_whole_output_without_down_shift(self):
        actor,bound=bound_actor()
        center=(640.,360.);old_center=(476.,324.)
        pose=tuple(Joint((center[0]-(p.y*720-old_center[1]))/1280,
                         (center[1]+(p.x*1280-old_center[0]))/720,p.confidence)
                   for p in actor.pose)
        box=(420.,260.,850.,450.)
        bound=bind_pose(pose,box,'DOWN')
        self.assertIsNotNone(bound)
        actor=replace(actor,pose=pose,action='DOWN',posture_fit=False,
                      bbox=tuple(v/(1280 if i%2==0 else 720) for i,v in enumerate(box)))
        shadow=contact_shadow_boxes((actor,),{actor.track_id:bound})[0]
        visible=[p for p in bound.joints if p.confidence>.25]
        head=bound.joints[0];height=bound.frame[3]-bound.frame[1]
        left=min(min(p.x for p in visible),head.x-bound.head_radius)
        right=max(max(p.x for p in visible),head.x+bound.head_radius)
        ground=max(max(p.y for p in visible),head.y+bound.head_radius*1.15)
        self.assertAlmostEqual((shadow[0]+shadow[2])*1280/2,(left+right)/2)
        self.assertAlmostEqual(shadow[1]*720,ground-height*.025)
        self.assertEqual(shadow,contact_shadow_boxes((replace(actor,action_mirror=True),),{actor.track_id:bound})[0])
        self.assertGreater((shadow[2]-shadow[0])*1280,250)

    def test_unbound_entities_keep_exact_previous_geometry(self):
        entities=(Entity('person','person',.5,.8,bbox=(.4,.2,.6,.8)),
                  Entity('car','car',.7,.9,bbox=(.6,.6,.8,.9)),
                  Entity('down','person',.2,.7,bbox=(.1,.5,.3,.7),action='DOWN'))
        old=contact_shadow_boxes(entities)
        self.assertEqual(old,contact_shadow_boxes(entities,{}))
        self.assertEqual(old,contact_shadow_boxes(entities,{'unrelated':bound_actor()[1]}))
        expected=(.42,.785,.58,.809)
        for actual,value in zip(old[0],expected):self.assertAlmostEqual(actual,value)

    def test_empty_and_predicted_targets_never_reuse_a_bound_shadow(self):
        actor,bound=bound_actor('CROUCH');mapping={actor.track_id:bound}
        self.assertTrue(contact_shadow_boxes((actor,),mapping))
        self.assertEqual(contact_shadow_boxes((),mapping),())
        self.assertEqual(contact_shadow_boxes((replace(actor,predicted=True),),mapping),())
        self.assertEqual(contact_shadow_boxes((actor,),{}),contact_shadow_boxes((actor,)))

    def test_upright_shadow_size_does_not_follow_extended_arms(self):
        actor,bound=bound_actor();joints=list(bound.joints)
        joints[15]=replace(joints[15],x=joints[15].x-300)
        stretched=replace(bound,joints=tuple(joints))
        self.assertEqual(contact_shadow_boxes((actor,),{actor.track_id:bound}),
                         contact_shadow_boxes((actor,),{actor.track_id:stretched}))

    def test_bound_shadow_is_clipped_to_viewport(self):
        actor,bound=bound_actor('CROUCH')
        delta=-470
        moved=replace(bound,joints=tuple(replace(p,x=p.x+delta) for p in bound.joints),
                      frame=(bound.frame[0]+delta,bound.frame[1],bound.frame[2]+delta,bound.frame[3]))
        shadow=contact_shadow_boxes((actor,),{actor.track_id:moved})[0]
        self.assertEqual(shadow[0],0)
        self.assertTrue(all(0<=v<=1 for v in shadow))


if __name__=='__main__':unittest.main()
