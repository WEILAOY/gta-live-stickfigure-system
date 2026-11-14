from pathlib import Path
import sys,unittest,time
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application,SOURCES
from stickfigure.core import Scene,Entity
from stickfigure.shooting import HeldWeapon,ShotEvent,ShotDetector
from stickfigure.hud import HudObservation

class QuietApp(Application):
    def _run_smoke(self):pass

class WeaponPresentationChecks(unittest.TestCase):
    def app(self):
        app=QuietApp(Path(__file__).resolve().parents[1],smoke_test=True)
        app.source_var.set(SOURCES[2]);app.person_action_var.set('自动姿态');app.auto_weapon_var.set(True)
        app.video_position=.5;app.auto_fire_var.set(True);app.update_idletasks();return app
    def scene(self):return Scene(0,0,1,.5,(Entity('p','person',.5,.9,bbox=(.4,.2,.6,.9)),),False)
    def test_holding_does_not_depend_on_flash_and_manual_material_still_works(self):
        app=self.app()
        try:
            app.fire_detector.holds['p']=HeldWeapon(app.video.generation,0,'p',.6,.4,1,0,(.5,.9),.95,'rifle')
            app.auto_fire_var.set(False)
            actor=app._presentation_scene(self.scene()).entities[0]
            self.assertFalse(actor.action_mirror);
            app.fire_detector.holds['p']=replace(app.fire_detector.holds['p'],dx=-1)
            self.assertTrue(app._presentation_scene(self.scene()).entities[0].action_mirror)
            self.assertEqual(actor.action,'GUN_HOLD');self.assertEqual(actor.weapon,'rifle');self.assertIsNotNone(actor.aim_point)
            walking=replace(self.scene(),entities=(replace(self.scene().entities[0],action='WALK'),))
            actor=app._presentation_scene(walking).entities[0]
            self.assertEqual(actor.action,'WALK');self.assertIsNone(actor.action_time)
            app.auto_weapon_var.set(False);app.weapon_var.set('手枪')
            self.assertEqual(app._presentation_scene(self.scene()).entities[0].weapon,'pistol')
            app.auto_fire_var.set(True)
            app._shot_effects={'p':(ShotEvent(app.video.generation,.5,'p',.6,.4,1,0,(.5,.9),.9),time.perf_counter())}
            app._unshown_shots={'p'};app.fire_detector.foreground_id='p';app.fire_detector.hud_observation=HudObservation('molotov',1,.95)
            app._poll_shots();self.assertFalse(app._shot_effects);self.assertFalse(app._unshown_shots)
        finally:app.close()
    def test_confirmed_flash_survives_slow_ui_until_successful_first_draw(self):
        app=self.app()
        try:
            event=ShotEvent(app.video.generation,.4,'p',.6,.4,1,0,(.5,.9),.95,'pistol')
            app._shot_effects={'p':(event,time.perf_counter()-.5)};app._unshown_shots={'p'}
            scene=app._presentation_scene(self.scene());actor=scene.entities[0]
            self.assertEqual(actor.action,'GUN_FIRE');self.assertEqual(actor.action_time,.05)
            app._mark_shots_presented(None);self.assertIn('p',app._unshown_shots)
            app.output_canvas.draw(scene);app._mark_shots_presented(scene);self.assertNotIn('p',app._unshown_shots)
            app._shot_effects={'p':(event,time.perf_counter()-.2)}
            self.assertEqual(app._presentation_scene(self.scene()).entities[0].action,'GUN_HOLD')
        finally:app.close()
    def test_finite_hold_and_reset_do_not_leave_a_permanent_gun(self):
        detector=ShotDetector(weapon_model=False,hud_enabled=False)
        detector.holds['p']=HeldWeapon(1,0,'p',.6,.4,1,0,(.5,.9),.95,'rifle')
        self.assertIn('p',detector.get_holds(1,.8));self.assertFalse(detector.get_holds(1,1.3))
        self.assertFalse(detector.get_holds(2,.8));detector.reset();self.assertFalse(detector.holds)

if __name__=='__main__':unittest.main()
