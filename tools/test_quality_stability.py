"""Cheap temporal corrections preserve current evidence and posture extents."""
from pathlib import Path
import sys,unittest
from dataclasses import replace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.vision import estimate_vehicle_view,stabilize_vehicle_yaw
from stickfigure.tracking import TrackManager,SceneSmoother,stable_material_size
from stickfigure.detection import Detection
from stickfigure.core import Entity,Scene


class QualityStabilityChecks(unittest.TestCase):
    def test_aligned_tail_lights_still_correct_a_slightly_oblique_view(self):
        rgb=np.full((400,640,3),80,np.uint8)
        crop=rgb[100:300,160:480]
        crop[145:151,60:68]=(255,0,0)
        crop[145:151,252:260]=(255,0,0)
        angle,confidence=estimate_vehicle_view(rgb,(.25,.25,.75,.75),12)
        self.assertEqual(angle,0)
        self.assertGreaterEqual(confidence,.55)
        corrected=stabilize_vehicle_yaw(12,angle,confidence,.2)
        self.assertLess(min(corrected,360-corrected),1)

    def test_small_box_width_changes_do_not_make_a_straight_car_wobble(self):
        rgb=np.full((400,640,3),80,np.uint8)
        yaw=0
        raw_angles=[]
        for width in (290,294,286,296,292,288):
            box=((320-width/2)/640,.25,(320+width/2)/640,.75)
            candidate,confidence=estimate_vehicle_view(rgb,box,yaw)
            raw_angles.append(candidate)
            yaw=stabilize_vehicle_yaw(yaw,candidate,confidence,.1)
            self.assertEqual(yaw,0)
        self.assertGreater(max(raw_angles),0)  # the observation actually varied

    def test_reliable_large_turn_is_prompt_and_independent_of_detection_cadence(self):
        slow=stabilize_vehicle_yaw(0,90,.6,.2)
        fast=0
        for _ in range(4):fast=stabilize_vehicle_yaw(fast,90,.6,.05)
        self.assertGreater(slow,88)
        self.assertAlmostEqual(slow,fast,places=6)
        self.assertLess(stabilize_vehicle_yaw(0,90,.32,.2),slow)

    def test_wrapped_angles_missing_evidence_and_repeated_timestamps(self):
        result=stabilize_vehicle_yaw(359,1,.6,.2)
        self.assertLess(abs(result-1),.1)
        self.assertEqual(stabilize_vehicle_yaw(35,180,.1,.3),35)
        self.assertEqual(stabilize_vehicle_yaw(35,180,.6,0),35)

    def test_tiny_scale_noise_is_reduced_without_moving_the_current_foot_anchor(self):
        tracker=TrackManager()
        initial=Detection('person',.9,(.4,.2,.6,.8))
        first=tracker.update([initial],0)[0]
        moved=replace(initial,box=(.41,.178,.618,.79))
        second=tracker.update([moved],.1)[0]
        a,b,c,d=second.render_box
        self.assertEqual(first.track_id,second.track_id)
        self.assertLess(abs((c-a)-.2),abs((moved.box[2]-moved.box[0])-.2))
        self.assertLess(abs((d-b)-.6),abs((moved.box[3]-moved.box[1])-.6))
        self.assertAlmostEqual((a+c)/2,(moved.box[0]+moved.box[2])/2)
        self.assertEqual(d,moved.box[3])

    def test_large_scale_changes_and_stale_history_are_adopted_directly(self):
        prior=(.4,.2,.6,.8)
        raw=(.38,.08,.62,.8)
        self.assertEqual(stable_material_size(raw,prior,.1),raw)
        small=(.398,.188,.602,.8)
        self.assertEqual(stable_material_size(small,prior,.8),small)

    def test_seated_down_and_viewport_edges_bypass_small_size_filter(self):
        for metadata in ({'seated':True,'action':'SIT'}, {'action':'DOWN','posture_hint':'DOWN'}):
            with self.subTest(metadata=metadata):
                tracker=TrackManager()
                first=tracker.update([Detection('person',.9,(.4,.2,.6,.8),**metadata)],0)[0]
                raw=(.398,.188,.602,.8)
                second=tracker.update([Detection('person',.9,raw,**metadata)],.1)[0]
                self.assertEqual(first.track_id,second.track_id)
                self.assertEqual(second.render_box,raw)
        tracker=TrackManager()
        tracker.update([Detection('person',.9,(.4,.2,.6,.8))],0)
        raw=(.398,.188,.602,.8)
        newly_seated=tracker.update([Detection('person',.9,raw,seated=True,action='SIT')],.1)[0]
        self.assertEqual(newly_seated.render_box,raw)
        tracker=TrackManager()
        tracker.update([Detection('person',.9,(.8,.2,1,.8))],0)
        second=tracker.update([Detection('person',.9,(.79,.188,1,.8))],.1)[0]
        self.assertEqual(second.render_box,(.79,.188,1,.8))

    def test_size_memory_does_not_allow_a_missing_person_to_be_drawn(self):
        tracker=TrackManager()
        tracker.update([Detection('person',.9,(.4,.2,.6,.8))],0)
        held=tracker.update([],.1)[0]
        self.assertTrue(held.predicted)
        entity=Entity(held.track_id,'person',.5,.8,bbox=held.box,
                      render_bbox=held.render_box,predicted=held.predicted)
        scene=Scene(1,0,1,0,(entity,),False,frame_clipping=True)
        self.assertFalse(SceneSmoother().update(scene,.1,.1).entities)


if __name__=='__main__':unittest.main()
