from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.assets import preset_pose,person_props,fallen_box
from stickfigure.combat import combat_scene
from stickfigure.core import Scene,Entity
from stickfigure.rendering import SceneCanvas

class CombatChecks(unittest.TestCase):
    def test_weapon_materials_are_distinct_and_grip_tracks_recoil(self):
        for weapon in ('pistol','rifle'):
            before=person_props('GUN_FIRE',0,weapon=weapon)
            after=person_props('GUN_FIRE',.15,weapon=weapon)
            dx=preset_pose('GUN_FIRE',.15)[16].x-preset_pose('GUN_FIRE',0)[16].x
            self.assertAlmostEqual(after[0].points[0]-before[0].points[0],dx)
            self.assertTrue(any(p.stroke=='#d58a2b' for p in before))
            self.assertFalse(any(p.stroke=='#d58a2b' for p in after))
            self.assertFalse(any(p.stroke=='#d58a2b' for p in person_props('GUN_HOLD',weapon=weapon)))
        self.assertNotEqual(person_props('GUN_HOLD',weapon='pistol'),person_props('GUN_HOLD',weapon='rifle'))

    def test_weapon_flash_is_short_and_does_not_persist_between_shots(self):
        for t,expected in ((0,True),(.05,True),(.10,True),(.12,False),(.3,False),(.46,True)):
            self.assertEqual(any(p.stroke=='#d58a2b' for p in person_props('GUN_FIRE',t)),expected)

    def test_fall_expands_sideways_and_holds_final_pose(self):
        start=preset_pose('FALL',0);end=preset_pose('FALL',.65)
        self.assertLess(start[0].y,end[0].y)
        self.assertGreater(end[0].x,start[0].x+.6)
        self.assertEqual(end,preset_pose('FALL',5))
        self.assertEqual(end,preset_pose('DOWN',0))
        self.assertEqual(preset_pose('DOWN',0),preset_pose('DOWN',20))
        box=fallen_box((100,100,160,300));self.assertEqual(box[2]-box[0],200)
        self.assertGreater(box[2],160)

    def test_expanded_fall_preserves_initial_anchor_for_both_directions(self):
        source=(100,100,160,300);center=130
        for mirror in (False,True):
            a,b,c,d=fallen_box(source,mirror)
            p=preset_pose('FALL',0,mirror)[0]
            self.assertAlmostEqual(a+p.x*(c-a),center)

    def test_manual_event_sequence_and_single_event_modes(self):
        expected=((0,'IDLE'),(1.1,'HIT'),(1.5,'FALL'),(2.2,'DOWN'),(30,'DOWN'))
        for t,action in expected:self.assertEqual(combat_scene(t).entities[1].action,action)
        self.assertEqual(combat_scene(.82).entities[0].action,'GUN_FIRE')
        self.assertEqual(combat_scene(1.1).entities[0].action,'GUN_HOLD')
        self.assertEqual(combat_scene(4,mode='fire').entities[1].action,'IDLE')
        self.assertEqual(combat_scene(.82,mode='hit').entities[0].action,'GUN_HOLD')
        self.assertEqual(combat_scene(4,mode='hit').entities[1].action,'DOWN')
        self.assertTrue(combat_scene(0).simulated)
        self.assertIn('非视频自动识别',combat_scene(0).notice)

    def test_guns_and_fall_are_frame_clipped_as_complete_presets(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            for x in (.02,.98):
                for mirror in (False,True):
                    scene=combat_scene(2.3,mirror=mirror)
                    target=replace(scene.entities[1],bbox=(x-.065,.25,x+.065,.85))
                    canvas.draw(replace(scene,entities=(target,)),simulated=True)
                    self.assertTrue(canvas._images)
                    for photo,box in canvas._layer_cache.values():
                        if photo is not None:self.assertTrue(0<=box[0]<box[2]<=640 and 0<=box[1]<box[3]<=360)
            scene=combat_scene(.82,weapon='rifle')
            canvas.draw(scene,simulated=True);before=canvas._images[0].tk.call(str(canvas._images[0]),'data','-format','png')
            canvas.draw(combat_scene(.97,weapon='rifle'),simulated=True)
            after=canvas._images[0].tk.call(str(canvas._images[0]),'data','-format','png')
            self.assertNotEqual(before,after)
        finally:root.destroy()

if __name__=='__main__':unittest.main()
