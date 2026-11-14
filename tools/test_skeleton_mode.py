"""Verify observable skeleton binding, settings, cache and viewport behavior."""
from pathlib import Path
import sys
import json
import tempfile
import unittest
import tkinter as tk
from dataclasses import replace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application, SOURCES
from stickfigure.assets import preset_pose, BODY_LINKS
from stickfigure.core import Joint, Entity, Scene, RunState
from stickfigure.rendering import SceneCanvas
from stickfigure.shooting import HeldWeapon

BASE = Path(__file__).resolve().parents[1]


def observed_pose(raised=False):
    """Two different observed arm positions share the same action label."""
    points = [Joint((545 + p.x * 190) / 1280, (65 + p.y * 500) / 720, p.confidence)
              for p in preset_pose('IDLE')]
    for index, (x, y) in ({14: (715, 185), 16: (770, 180)} if not raised
                         else {14: (720, 110), 16: (740, 45)}).items():
        points[index] = Joint(x / 1280, y / 720, 1.)
    return tuple(points)


def actor(**changes):
    value = Entity('person-1', 'person', .5, .85, bbox=(.42, .08, .58, .85),
                   pose=observed_pose(), action='IDLE')
    return replace(value, **changes)


class SkeletonRendererChecks(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.canvas = SceneCanvas(self.root, width=640, height=360)
        self.canvas.pack()
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def scene(self, person=None, **changes):
        return replace(Scene(1, 0., 1, 0., (person or actor(),), False,
                             frame_clipping=True, skeleton_binding=True), **changes)

    def test_binding_uses_observed_joint_changes_and_invalidates_sprite(self):
        first = self.scene()
        self.canvas.draw(first)
        self.assertTrue(self.canvas.find_withtag('skeleton-person'))
        self.assertTrue(self.canvas.find_withtag('preset-object'))
        joints = tuple(self.canvas._poses['person-1'][0])
        photo = self.canvas._images[0]
        self.canvas.draw(first)
        self.assertIs(self.canvas._images[0], photo)
        second = self.scene(actor(pose=observed_pose(True)))
        self.canvas.draw(second)
        self.assertTrue(self.canvas.find_withtag('skeleton-person'))
        self.assertIsNot(self.canvas._images[0], photo)
        changed = self.canvas._poses['person-1'][0]
        self.assertGreater(abs(changed[16][1] - joints[16][1]), 10)
        self.assertEqual(first.entities[0].action, second.entities[0].action)

    def test_disabled_binding_keeps_original_preset_despite_raw_pose_change(self):
        first = self.scene(skeleton_binding=False)
        self.canvas.draw(first)
        joints = tuple(self.canvas._poses['person-1'][0])
        photo = self.canvas._images[0]
        self.canvas.draw(self.scene(actor(pose=observed_pose(True)), skeleton_binding=False))
        self.assertFalse(self.canvas.find_withtag('skeleton-person'))
        self.assertEqual(tuple(self.canvas._poses['person-1'][0]), joints)
        self.assertIs(self.canvas._images[0], photo)

    def test_switch_off_then_on_restores_current_bound_pose(self):
        bound = self.scene()
        self.canvas.draw(bound)
        joints = tuple(self.canvas._poses['person-1'][0])
        self.canvas.draw(replace(bound, skeleton_binding=False))
        self.assertFalse(self.canvas.find_withtag('skeleton-person'))
        self.assertNotEqual(tuple(self.canvas._poses['person-1'][0]), joints)
        self.canvas.draw(bound)
        self.assertTrue(self.canvas.find_withtag('skeleton-person'))
        self.assertEqual(tuple(self.canvas._poses['person-1'][0]), joints)

    def test_translation_reuses_bound_sprite_and_moves_all_output_joints(self):
        person = actor()
        self.canvas.draw(self.scene(person))
        image = self.canvas._images[0]
        before = tuple(self.canvas._poses[person.track_id][0])
        dx, dy = .025, .05
        translated = replace(person, x=person.x + dx, y=person.y + dy,
            bbox=tuple(v + (dx if i % 2 == 0 else dy) for i, v in enumerate(person.bbox)),
            pose=tuple(replace(p, x=p.x + dx, y=p.y + dy) for p in person.pose))
        self.canvas.draw(self.scene(translated))
        self.assertIs(self.canvas._images[0], image)
        after = self.canvas._poses[person.track_id][0]
        for old, new in zip(before, after):
            if old[2] > .25:
                self.assertAlmostEqual(new[0] - old[0], 1280 * dx)
                self.assertAlmostEqual(new[1] - old[1], 720 * dy)

    def test_manual_and_automatic_guns_keep_existing_grips(self):
        for manual in (True, False):
            with self.subTest(manual=manual):
                person = actor(action='GUN_HOLD', action_manual=manual,
                               aim_point=None if manual else (.61, .37),
                               aim_direction=(1., -.1), weapon='rifle')
                scene = self.scene(person, skeleton_binding=False)
                self.canvas.draw(scene)
                image = self.canvas._images[0]
                original = tuple(self.canvas._poses.get(person.track_id, ((), 0))[0])
                self.canvas.draw(replace(scene, skeleton_binding=True,
                                         entities=(replace(person, pose=observed_pose(True)),)))
                self.assertFalse(self.canvas.find_withtag('skeleton-person'))
                self.assertIs(self.canvas._images[0], image)
                if not manual:
                    self.assertEqual(tuple(self.canvas._poses[person.track_id][0]), original)

    def test_manual_action_and_missing_pose_use_complete_presets(self):
        for person in (actor(action='RAISE', action_manual=True), actor(pose=())):
            with self.subTest(manual=person.action_manual):
                self.canvas.draw(self.scene(person))
                self.assertFalse(self.canvas.find_withtag('skeleton-person'))
                self.assertTrue(self.canvas.find_withtag('preset-object'))
                points = self.canvas._poses['person-1'][0]
                self.assertTrue(all(points[i][2] > .25 for link in BODY_LINKS for i in link))

    def test_lost_joint_never_removes_a_body_segment(self):
        points = list(observed_pose())
        for index in (13, 15, 25, 27):
            points[index] = replace(points[index], confidence=0.)
        self.canvas.draw(self.scene(actor(pose=tuple(points))))
        self.assertTrue(self.canvas.find_withtag('preset-object'))
        target = self.canvas._poses['person-1'][0]
        self.assertTrue(all(target[i][2] > .25 for link in BODY_LINKS for i in link))

    def test_sprite_covers_retargeted_limbs_and_clips_only_to_viewport(self):
        person = actor(pose=observed_pose(True))
        self.canvas.draw(self.scene(person))
        # Every currently visible joint must be inside its local image rather
        # than cropped by the original narrow detection box.
        left, top, right, bottom, _ = self.canvas.hitboxes[0]
        for x, y, confidence in self.canvas._poses['person-1'][0]:
            if confidence > .25 and 0 <= x < 1280 and 0 <= y < 720:
                self.assertTrue(left <= x / 2 <= right and top <= y / 2 <= bottom,
                                (x, y, (left, top, right, bottom)))
        for dx, dy in ((-.48, 0.), (.48, 0.), (0., -.60), (0., .60)):
            moved = replace(person, x=person.x + dx, y=person.y + dy,
                            bbox=tuple(value + (dx if i % 2 == 0 else dy)
                                       for i, value in enumerate(person.bbox)),
                            pose=tuple(replace(p, x=p.x + dx, y=p.y + dy)
                                       for p in person.pose))
            self.canvas.draw(self.scene(moved))
            for photo, bounds in self.canvas._layer_cache.values():
                if photo:
                    self.assertTrue(0 <= bounds[0] < bounds[2] <= 640)
                    self.assertTrue(0 <= bounds[1] < bounds[3] <= 360)

    def test_missing_target_and_epoch_change_cannot_restore_old_rig(self):
        scene = self.scene()
        self.canvas.draw(scene)
        image = self.canvas._images[0]
        self.canvas.draw(replace(scene, entities=()))
        self.assertFalse(self.canvas.find_withtag('skeleton-person'))
        self.assertFalse(self.canvas._poses)
        self.canvas.draw(self.scene(actor(predicted=True)))
        self.assertFalse(self.canvas.find_withtag('preset-object'))
        self.canvas.draw(replace(scene, scene_epoch=2))
        self.assertIsNot(self.canvas._images[0], image)


class SkeletonApplicationChecks(unittest.TestCase):
    def setUp(self):
        class App(Application):
            def _run_smoke(self):
                pass
        self.app = App(BASE, smoke_test=True)
        # Native window mapping needs one event pass on Windows; idletasks
        # alone can leave the independently mapped output canvas at 1x1.
        self.app.output.geometry('640x360+0+0')
        self.app.update()
        self.folder = tempfile.TemporaryDirectory(dir=BASE / 'runtime/smoke')
        self.app.settings_path = Path(self.folder.name) / 'settings.json'
        self.mocks = []
        for worker in (self.app.detector, self.app.road_worker, self.app.text_worker):
            mocked = patch.object(worker, 'submit')
            self.mocks.append(mocked)
            mocked.start()
        self.app.source_var.set(SOURCES[2])
        self.app.state_value = RunState.PAUSED
        self.app.person_action_var.set('自动姿态')
        self.app.scene = Scene(1, 0., 1, 0., (actor(),), False)
        self.app.update_idletasks()

    def tearDown(self):
        for ident in self.app.tk.call('after', 'info'):
            self.app.after_cancel(ident)
        self.app.close()
        for mocked in self.mocks:
            mocked.stop()
        self.folder.cleanup()

    def test_toggle_saves_boolean_and_does_not_resubmit_or_reset_detection(self):
        a = self.app
        epoch, generation = a.detector.epoch, a.video.generation
        source = a.scene
        for enabled in (True, False):
            a.skeleton_var.set(enabled)
            a._skeleton_changed()
            self.assertIs(a._load_settings()['skeleton_binding'], enabled)
            self.assertIs(a._presentation_scene(source).skeleton_binding, enabled)
            self.assertEqual((a.detector.epoch, a.video.generation), (epoch, generation))
            self.assertIs(a.scene, source)
        for worker in (a.detector, a.road_worker, a.text_worker):
            worker.submit.assert_not_called()

    def test_invalid_saved_values_are_ignored(self):
        a = self.app
        for value in ('true', 'false', 1, [], None):
            a.settings_path.write_text(json.dumps({'skeleton_binding': value}), encoding='utf-8')
            self.assertNotIn('skeleton_binding', a._load_settings())
        for value in (True, False):
            a.settings_path.write_text(json.dumps({'skeleton_binding': value}), encoding='utf-8')
            self.assertIs(a._load_settings()['skeleton_binding'], value)

    def test_manual_action_stays_authoritative_with_binding_enabled(self):
        a = self.app
        a.skeleton_var.set(True)
        a.person_action_var.set('抬手')
        presented = a._presentation_scene(a.scene)
        self.assertTrue(presented.skeleton_binding)
        self.assertTrue(presented.entities[0].action_manual)
        self.assertEqual(presented.entities[0].action, 'RAISE')
        self.assertFalse(presented.entities[0].pose)
        a.output_canvas.draw(presented, simulated=False)
        self.assertFalse(a.output_canvas.find_withtag('skeleton-person'))

    def test_first_person_auto_gun_does_not_override_next_person_pose(self):
        a = self.app
        first = actor()
        second = replace(first, track_id='person-2', x=.7,
                         bbox=tuple(v + .2 if i % 2 == 0 else v for i, v in enumerate(first.bbox)),
                         pose=tuple(replace(p, x=p.x + .2) for p in first.pose))
        a.scene = replace(a.scene, entities=(first, second))
        a.skeleton_var.set(True)
        a.fire_detector.holds[first.track_id] = HeldWeapon(a.video.generation, 0., first.track_id,
            .6, .37, 1., 0., (first.x, first.y), .95, 'rifle')
        scene = a._presentation_scene(a.scene)
        p1, p2 = scene.entities
        self.assertEqual(p1.action, 'GUN_HOLD')
        self.assertFalse(p1.pose)
        self.assertIsNotNone(p1.aim_point)
        self.assertFalse(p2.action_manual)
        self.assertEqual(p2.action, 'IDLE')
        self.assertEqual(len(p2.pose), len(second.pose))
        for actual, expected in zip(p2.pose, second.pose):
            self.assertAlmostEqual(actual.x, expected.x)
            self.assertAlmostEqual(actual.y, expected.y)
            self.assertEqual(actual.confidence, expected.confidence)
        a.output_canvas.draw(scene, simulated=False)
        self.assertTrue(a.output_canvas.find_withtag('skeleton-person'))


if __name__ == '__main__':
    unittest.main()
