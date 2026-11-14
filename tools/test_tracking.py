from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from stickfigure.detection import Detection
from stickfigure.tracking import TrackManager,SceneSmoother
from stickfigure.core import Scene,Entity


class TrackingChecks(unittest.TestCase):
    def detection(self,x=.1,label='person'):
        return Detection(label,.9,(x,.25,x+.10,.65))

    def test_order_does_not_define_identity(self):
        manager=TrackManager()
        first=manager.update([self.detection(.1),self.detection(.7)],0)
        second=manager.update([self.detection(.69),self.detection(.11)],.2)
        self.assertEqual(second[0].track_id,first[1].track_id)
        self.assertEqual(second[1].track_id,first[0].track_id)

    def test_vehicle_subtype_change_cannot_leave_three_overlapping_tracks(self):
        manager=TrackManager()
        ids=[]
        for i,label in enumerate(('car','truck','bus','car','truck')):
            result=manager.update([self.detection(.4,label)],i*.1)
            self.assertEqual(len(result),1)
            self.assertFalse(result[0].predicted)
            ids.append(result[0].track_id)
        self.assertEqual(len(set(ids)),1)

    def test_weak_single_frame_candidate_needs_confirmation(self):
        manager=TrackManager()
        weak=Detection('car',.35,(.2,.3,.5,.6))
        first=manager.update([weak],0)[0]
        self.assertFalse(first.confirmed)
        held=manager.update([],.1)[0]
        self.assertTrue(held.predicted)
        self.assertFalse(held.confirmed)
        again=manager.update([weak],.2)[0]
        self.assertTrue(again.confirmed)
        self.assertEqual(again.track_id,first.track_id)

    def test_occlusion_retains_identity_then_expires(self):
        manager=TrackManager()
        ident=manager.update([self.detection()],0)[0].track_id
        missing=manager.update([],.2)[0]
        self.assertTrue(missing.predicted)
        self.assertAlmostEqual(missing.missing_age,.2)
        self.assertEqual(manager.update([self.detection(.12)],.4)[0].track_id,ident)
        self.assertFalse(manager.update([],1.5))
        self.assertNotEqual(manager.update([self.detection(.12)],1.6)[0].track_id,ident)

    def test_camera_translation_does_not_become_relative_speed(self):
        manager=TrackManager()
        first=manager.update([self.detection(.1)],0)[0]
        second=manager.update([self.detection(.35)],.2,((1,0,.25),(0,1,0)))[0]
        self.assertEqual(first.track_id,second.track_id)
        velocity=manager.tracks[first.track_id].relative_velocity
        self.assertAlmostEqual(velocity[0],0,places=6)

    def test_different_class_or_far_target_does_not_steal_id(self):
        manager=TrackManager()
        ident=manager.update([self.detection()],0)[0].track_id
        result=manager.update([self.detection(.1,'car')],.2)
        self.assertNotEqual(result[0].track_id,ident)
        manager.clear()
        first=manager.update([self.detection(.1)],1)[0]
        second=manager.update([self.detection(.8)],1.2)[0]
        self.assertNotEqual(first.track_id,second.track_id)

    def test_prediction_is_bounded_and_pause_does_not_advance(self):
        smoother=SceneSmoother()
        entity=Entity('a','car',.5,.7,bbox=(.4,.4,.6,.7),velocity=(.5,0),sample_time=0)
        scene=Scene(1,0,1,0,(entity,),False)
        result=smoother.update(scene,10,1,True)
        self.assertLessEqual(result.entities[0].x,.59+1e-6)
        paused=smoother.update(scene,10,1.1,False)
        self.assertAlmostEqual(paused.entities[0].x,.5)

    def test_held_target_hidden_after_short_prediction_window(self):
        smoother=SceneSmoother()
        entity=Entity('a','car',.5,.7,bbox=(.4,.4,.6,.7),predicted=True,missing_age=.3,sample_time=0)
        scene=Scene(1,0,1,0,(entity,),False)
        self.assertTrue(smoother.update(scene,0,1,True).entities)
        self.assertFalse(smoother.update(scene,.1,1.1,True).entities)


if __name__=='__main__':
    unittest.main()
