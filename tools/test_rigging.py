"""Observed joint directions control a complete, fixed-length figure."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import FrozenInstanceError,replace
import math
import unittest
from stickfigure.assets import bind_pose,bound_person_props,preset_pose,person_pose,BODY_LINKS
from stickfigure.core import Joint


BOX=(400.,100.,552.,500.)


def input_pose(action='IDLE',box=BOX,mirror=False):
    a,b,c,d=box
    return tuple(Joint((a+p.x*(c-a))/1280,(b+p.y*(d-b))/720,p.confidence)
                 for p in person_pose(action,0,mirror))


def move(pose,index,x,y,confidence=1):
    result=list(pose);result[index]=Joint(x/1280,y/720,confidence);return tuple(result)


class RiggingChecks(unittest.TestCase):
    def test_fixed_idle_material_round_trip_and_immutable_result(self):
        bound=bind_pose(input_pose(),BOX)
        self.assertIsNotNone(bound)
        self.assertEqual(len(bound.joints),33)
        for actual,expected in zip(bound.joints,input_pose()):
            if expected.confidence:
                self.assertAlmostEqual(actual.x,expected.x*1280,places=6)
                self.assertAlmostEqual(actual.y,expected.y*720,places=6)
        self.assertAlmostEqual(bound.frame[2]-bound.frame[0],.38*(bound.frame[3]-bound.frame[1]))
        with self.assertRaises(FrozenInstanceError):bound.head_radius=4

    def test_observed_arm_directions_change_without_stretching_any_bone(self):
        source=input_pose();first=bind_pose(source,BOX)
        changed=move(move(source,14,605,175),16,640,70)
        second=bind_pose(changed,BOX)
        self.assertNotEqual(first.joints[14],second.joints[14])
        self.assertNotEqual(first.joints[16],second.joints[16])
        height=second.frame[3]-second.frame[1];ref=preset_pose('IDLE')
        for a,b in BODY_LINKS:
            actual=math.hypot(second.joints[b].x-second.joints[a].x,second.joints[b].y-second.joints[a].y)
            expected=math.hypot((ref[b].x-ref[a].x)*.38,ref[b].y-ref[a].y)*height
            self.assertAlmostEqual(actual,expected,places=6)

    def test_direction_uses_physical_width_height_ratio(self):
        source=input_pose();shoulder=source[11]
        # Equal normalized deltas are not a 45-degree screen-space direction.
        source=list(source);source[13]=Joint(shoulder.x-.05,shoulder.y+.05,1)
        bound=bind_pose(tuple(source),BOX)
        x=bound.joints[13].x-bound.joints[11].x;y=bound.joints[13].y-bound.joints[11].y
        self.assertAlmostEqual(x/y,-1280/720,places=6)

    def test_missing_limb_observation_keeps_complete_preset_direction(self):
        source=input_pose('RAISE');source=list(source)
        for i in (13,14,15,16,25,26,27,28,29,30,31,32):source[i]=replace(source[i],confidence=0)
        bound=bind_pose(tuple(source),BOX,action='RAISE')
        self.assertIsNotNone(bound)
        for a,b in BODY_LINKS:
            self.assertEqual(bound.joints[a].confidence,1)
            self.assertEqual(bound.joints[b].confidence,1)
        self.assertLess(bound.joints[15].y,bound.joints[11].y)
        self.assertLess(bound.joints[16].y,bound.joints[12].y)

    def test_missing_torso_falls_back_to_legacy_body(self):
        for index in (11,12,23,24):
            source=list(input_pose());source[index]=replace(source[index],confidence=.1)
            self.assertIsNone(bind_pose(tuple(source),BOX))
        self.assertIsNone(bind_pose((),BOX))

    def test_invalid_landmarks_do_not_poison_output(self):
        for value in (float('nan'),float('inf'),1e100):
            source=list(input_pose());source[13]=Joint(value,.4,1)
            bound=bind_pose(tuple(source),BOX)
            self.assertIsNotNone(bound)
            self.assertTrue(all(math.isfinite(v) for p in bound.joints for v in (p.x,p.y,p.confidence)))
            source[11]=Joint(value,.4,1)
            self.assertIsNone(bind_pose(tuple(source),BOX))
        self.assertIsNone(bind_pose(input_pose(),(0,0,float('nan'),720)))
        self.assertIsNone(bind_pose(input_pose(),(0,0,0,720)))

    def test_tiny_torso_and_implausible_remote_body_fall_back(self):
        source=list(input_pose());source[23]=replace(source[11],y=source[11].y+.001)
        source[24]=replace(source[12],y=source[12].y+.001)
        self.assertIsNone(bind_pose(tuple(source),BOX))
        remote=tuple(replace(p,x=p.x+2) for p in input_pose())
        self.assertIsNone(bind_pose(remote,BOX))

    def test_limb_lengths_independent_of_observed_arm_length(self):
        source=input_pose();a=move(source,13,source[11].x*1280-10,source[11].y*720+10)
        b=move(source,13,source[11].x*1280-80,source[11].y*720+80)
        first,second=bind_pose(a,BOX),bind_pose(b,BOX)
        self.assertAlmostEqual(first.joints[13].x,second.joints[13].x)
        self.assertAlmostEqual(first.joints[13].y,second.joints[13].y)

    def test_extending_arms_expand_art_bounds_without_clamping(self):
        source=input_pose();source=move(move(source,13,350,180),15,255,165)
        bound=bind_pose(source,BOX)
        self.assertLess(bound.joints[15].x,BOX[0])
        self.assertLess(bound.bounds[0],bound.joints[15].x)
        self.assertLessEqual(bound.bounds[0],bound.joints[0].x-bound.head_radius)
        self.assertGreaterEqual(bound.bounds[3],max(p.y for p in bound.joints if p.confidence))

    def test_observed_torso_rotation_rotates_fixed_head_and_body(self):
        source=input_pose();center=(476.,324.)
        turned=[]
        for p in source:
            x,y=p.x*1280-center[0],p.y*720-center[1]
            turned.append(Joint((center[0]-y)/1280,(center[1]+x)/720,p.confidence))
        bound=bind_pose(tuple(turned),(240,230,650,420))
        self.assertIsNotNone(bound)
        hips=tuple((getattr(bound.joints[23],k)+getattr(bound.joints[24],k))/2 for k in ('x','y'))
        self.assertGreater(bound.joints[0].x,hips[0])
        self.assertAlmostEqual(bound.joints[0].y,hips[1])

    def test_body_height_is_bounded_by_complete_figure_extent(self):
        source=input_pose(box=(440,110,510,410))
        bound=bind_pose(source,(440,160,510,360))
        self.assertIsNotNone(bound)
        self.assertLessEqual(bound.frame[3]-bound.frame[1],1.35*200)

    def test_fixed_props_follow_matching_output_wrist(self):
        for action in ('PHONE','PHONE_LOOK','DRINK'):
            for mirrored in (False,True):
                first=bind_pose(input_pose(action,mirror=mirrored),BOX,action,mirrored)
                changed=move(input_pose(action,mirror=mirrored),16,510,125)
                second=bind_pose(changed,BOX,action,mirrored)
                shapes1=bound_person_props(first,action,mirrored)
                shapes2=bound_person_props(second,action,mirrored)
                self.assertEqual(len(shapes1),len(shapes2))
                dx=second.joints[16].x-first.joints[16].x;dy=second.joints[16].y-first.joints[16].y
                for s1,s2 in zip(shapes1,shapes2):
                    self.assertEqual((s1.kind,s1.fill,s1.stroke,s1.width),(s2.kind,s2.fill,s2.stroke,s2.width))
                    for i,(a,b) in enumerate(zip(s1.points,s2.points)):
                        self.assertAlmostEqual(b-a,dx if i%2==0 else dy)
        self.assertEqual(bound_person_props(first,'IDLE'),())


if __name__=='__main__':unittest.main()
