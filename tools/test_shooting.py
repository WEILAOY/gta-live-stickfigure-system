from pathlib import Path
import sys,unittest
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.core import Joint
from stickfigure.detection import Detection
from stickfigure.video import VideoFrame
from stickfigure.shooting import ShotDetector
from stickfigure.assets import combat_drawing,aimed_gun_drawing

class ShootingChecks(unittest.TestCase):
    def setUp(self):
        self.detector=ShotDetector(weapon_model=False,hud_enabled=False);self.detector.set_enabled(True)
        pose=[Joint(.5,.5,0) for _ in range(33)]
        pose[15]=Joint(.48,.50);pose[16]=Joint(.47,.51)
        self.person=Detection('person',.95,(.32,.2,.62,.95),'player',pose=tuple(pose),confirmed=True,weapon_boxes=((.48,.47,.53,.52),))
        self.base=np.random.default_rng(5).integers(30,80,(240,426,3),dtype=np.uint8)
        self.detector.set_targets((self.person,),1,0)
    def frame(self,t,point=None,color=(255,210,70),generation=1):
        image=self.base.copy()
        if point:cv2.rectangle(image,(point[0]-2,point[1]-2),(point[0]+2,point[1]+2),color,-1)
        return VideoFrame(generation,t,426,240,image.tobytes())
    def test_temporal_burst_near_hand_emits_coordinates_once(self):
        self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119)))
        event=self.detector.events.get_nowait()
        self.assertEqual(event.owner,'player');self.assertAlmostEqual(event.x,216/426,delta=.01)
        self.detector.process(self.frame(.066,(216,119)))
        self.assertTrue(self.detector.events.empty());self.assertFalse(self.detector.last_error)
    def test_skin_and_far_lights_are_not_gunfire(self):
        for point,color in (((216,119),(225,180,100)),((330,119),(255,210,70)),((216,215),(255,210,70))):
            self.detector.reset();self.detector.set_targets((self.person,),1,0)
            self.detector.process(self.frame(0));self.detector.process(self.frame(.033,point,color))
            self.assertTrue(self.detector.events.empty(),(point,color))
    def test_missing_and_predicted_people_do_not_fire(self):
        for people in ((),(replace(self.person,predicted=True),),(replace(self.person,confirmed=False),)):
            self.detector.reset();self.detector.set_targets(people,1,0)
            self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119)))
            self.assertTrue(self.detector.events.empty())
    def test_cut_generation_and_stale_targets_reject_old_ownership(self):
        self.detector.process(self.frame(0))
        self.detector.process(VideoFrame(1,.033,426,240,np.full_like(self.base,255).tobytes()))
        self.assertTrue(self.detector.events.empty())
        self.detector.reset();self.detector.set_targets((self.person,),1,0)
        self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119),generation=2))
        self.assertTrue(self.detector.events.empty())
        self.detector.process(self.frame(.9,generation=1));self.detector.process(self.frame(.933,(216,119)))
        self.assertTrue(self.detector.events.empty())
    def test_disable_clears_pending_events(self):
        self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119)))
        self.assertFalse(self.detector.events.empty());self.detector.set_enabled(False)
        self.assertTrue(self.detector.events.empty());self.assertIsNone(self.detector.previous)
    def test_hand_brightness_without_observed_gun_never_fires(self):
        self.detector.reset()
        self.detector.set_targets((replace(self.person,weapon_boxes=()),),1,0)
        self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119)))
        self.assertTrue(self.detector.events.empty())
    def test_gun_elsewhere_and_no_wrist_cannot_claim_a_shot(self):
        for person in (replace(self.person,weapon_boxes=((.34,.22,.40,.29),)),replace(self.person,pose=())):
            self.detector.reset();self.detector.set_targets((person,),1,0)
            self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119)))
            self.assertTrue(self.detector.events.empty())
    def test_large_fire_region_is_rejected_even_near_gun(self):
        self.detector.process(self.frame(0));image=self.base.copy()
        cv2.rectangle(image,(200,100),(240,140),(255,170,30),-1)
        self.detector.process(VideoFrame(1,.033,426,240,image.tobytes()))
        self.assertTrue(self.detector.events.empty())
    def test_late_model_result_matches_buffer_once_without_raw_frame_replay(self):
        self.detector.reset()
        self.detector.process(self.frame(0));self.detector.process(self.frame(.033,(216,119)))
        self.assertTrue(self.detector.events.empty());self.assertTrue(self.detector.pending)
        self.detector.set_targets((self.person,),1,0)
        self.assertEqual(self.detector.events.get_nowait().owner,'player')
        self.detector.set_targets((self.person,),1,0);self.assertTrue(self.detector.events.empty())
    def test_persistent_hot_neighborhood_flicker_is_not_a_new_muzzle_burst(self):
        image=self.base.copy();image[112:114,210:213]=(255,210,70)
        self.detector.process(VideoFrame(1,0,426,240,image.tobytes()))
        self.detector.process(self.frame(.033,(216,119)))
        self.assertTrue(self.detector.events.empty())
    def test_combat_body_and_guns_use_sparse_lines(self):
        for weapon,count in (('pistol',3),('rifle',6)):
            for yaw in (0,35,90,180):
                shapes=combat_drawing('GUN_HOLD',0,weapon,yaw).shapes
                self.assertEqual(sum(s.role=='weapon' for s in shapes),count)
                self.assertFalse(any(s.kind=='polygon' for s in shapes))
    def test_aimed_flash_attachment_and_clear(self):
        for direction in ((1,0),(-1,0),(0,-1)):
            shapes,hands=aimed_gun_drawing('pistol',(400,250),direction,120,'GUN_FIRE',.05)
            flash=[s for s in shapes if s.role=='muzzle-flash'];self.assertTrue(flash)
            self.assertEqual(len(hands),2)
            self.assertFalse(any(s.role=='muzzle-flash' for s in aimed_gun_drawing('pistol',(400,250),direction,120,'GUN_HOLD',0)[0]))
            self.assertLess(min(abs(s.points[0]-400)+abs(s.points[1]-250) for s in flash),12)

if __name__=='__main__':unittest.main()
