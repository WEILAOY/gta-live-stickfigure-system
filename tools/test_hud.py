from pathlib import Path
import sys,unittest
from dataclasses import replace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.hud import WeaponHud,HudObservation
from stickfigure.shooting import ShotDetector,ShotEvent,HeldWeapon
from stickfigure.detection import Detection

class HudChecks(unittest.TestCase):
    def setUp(self):
        self.hud=WeaponHud(Path(__file__).resolve().parents[1]/'models/hud')
    def feed(self,ammo,t,weapon='rifle',generation=1):
        self.hud.inspect=lambda rgb:HudObservation(weapon,ammo,.95)
        return self.hud.update(None,generation,t)[1]
    def test_stable_hold_never_fires_and_ammo_decrease_requires_confirmation(self):
        for i in range(15):self.assertFalse(self.feed(30,i/30))
        self.assertFalse(self.feed(29,.5));self.assertTrue(self.feed(29,.533))
        self.assertFalse(self.feed(29,.566))
    def test_first_shot_after_long_idle_and_reload_are_distinct(self):
        for i in range(100):self.assertFalse(self.feed(8,i/30))
        self.assertFalse(self.feed(7,100/30));self.assertTrue(self.feed(7,101/30))
        self.assertFalse(self.feed(30,102/30));self.assertFalse(self.feed(30,103/30))
    def test_generation_switch_molotov_and_large_jump_do_not_fire(self):
        for i in range(4):self.feed(30,i/30)
        for i in range(4,7):self.assertFalse(self.feed(1,i/30))
        for i in range(7,10):self.assertFalse(self.feed(0,i/30,'molotov'))
        for i in range(10,13):self.assertFalse(self.feed(2,i/30,'pistol',generation=2))
    def test_unknown_layout_is_ignored(self):
        for value in (0,100,255):self.assertIsNone(self.hud.inspect(np.full((480,852,3),value,np.uint8)))
    def test_hud_only_binds_visible_confirmed_foreground_person(self):
        detector=ShotDetector(weapon_model=False,hud_enabled=False)
        detector.hud_observation=HudObservation('rifle',30,.95);detector.hud_generation=1;detector.hud_time=.1
        person=Detection('person',.9,(.2,.6,.4,1),'player')
        detector.set_targets((person,),1,0)
        self.assertEqual(detector.get_holds(1,.1)['player'].weapon_type,'rifle')
        self.assertTrue(detector.events.empty())
        detector.hud_shots.append((1,.1,'rifle'));detector._bind_hud()
        self.assertEqual(detector.events.get_nowait().weapon_type,'rifle')
        detector.set_targets((replace(person,predicted=True),),1,.2)
        self.assertFalse(detector.get_holds(1,.2))
    def test_molotov_clears_foreground_hold(self):
        detector=ShotDetector(weapon_model=False,hud_enabled=False)
        person=Detection('person',.9,(.2,.6,.4,1),'player')
        detector.hud_observation=HudObservation('pistol',17,.95);detector.hud_generation=1;detector.hud_time=.1
        detector.set_targets((person,),1,0);self.assertTrue(detector.holds)
        detector.hud_observation=HudObservation('molotov',1,.95);detector._bind_hud()
        self.assertFalse(detector.holds);self.assertTrue(detector.events.empty())
    def test_background_person_does_not_inherit_player_gun(self):
        detector=ShotDetector(weapon_model=False,hud_enabled=False)
        detector.hud_observation=HudObservation('rifle',30,.95);detector.hud_generation=1;detector.hud_time=.1
        detector.set_targets((Detection('person',.9,(.6,.3,.7,.7),'npc'),),1,0)
        self.assertFalse(detector.holds)

if __name__=='__main__':unittest.main()
