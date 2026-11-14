"""Exercise real pose data, paused binding, playback motion, seek and stop."""
from pathlib import Path
import sys
import json
import time
import math
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.core import RunState

base = Path(__file__).resolve().parents[1]
out = base.parent.parent / 'skeleton-workflow'
out.mkdir(parents=True, exist_ok=True)
source = base.parent / '03_测试素材/gta6_actions_test.mp4'


class TestApp(Application):
    def _run_smoke(self):
        pass


app = TestApp(base, smoke_test=True, initial_video=str(source), initial_position=40.)
app.ai_var.set(True)
for option in (app.road_var, app.buildings_var, app.sky_var, app.shading_var,
               app.color_var, app.text_var, app.auto_fire_var):
    option.set(False)
app.person_action_var.set('自动姿态')
app.skeleton_var.set(False)
app.detect_rate_var.set('10')
app._detection_changed()
app._road_changed()
saved_settings = app.settings_path
app.settings_path = out / 'settings.json'
state = 'initial_paused'
started = time.perf_counter()
playing_from = None
last_sample = None
previous_bones = {}
motion_tracks = set()
input_times = set()
angle_matches = 0
records = []
paused_samples = []
submissions = [0]
original_submit = app.detector.submit


def count_submit(*args, **kwargs):
    submissions[0] += 1
    return original_submit(*args, **kwargs)


app.detector.submit = count_submit


def render():
    scene = app._presentation_scene(app.scene)
    app.output_canvas.draw(scene, simulated=False)
    return scene


def ready():
    return bool(app.scene and app.video_frame and app._detection_is_current()
                and app.output_canvas.winfo_width() > 100
                and any(e.kind == 'person' and len(e.pose) == 33 for e in app.scene.entities))


def record(label, **extra):
    records.append(dict(stage=label, position=app.video_position,
                        generation=app.video.generation, detector_epoch=app.detector.epoch,
                        **extra))


def toggle(enabled):
    identity = app.detection_result
    old_epoch = app.detector.epoch
    old_generation = app.video.generation
    old_submissions = submissions[0]
    old_position = app.video_position
    app.skeleton_var.set(enabled)
    app._skeleton_changed()
    assert app.detection_result is identity
    assert app.detector.epoch == old_epoch and app.video.generation == old_generation
    assert submissions[0] == old_submissions, 'The binding toggle submitted another model job'
    assert app.video_position == old_position
    assert app._load_settings()['skeleton_binding'] is enabled
    return render()


def direction(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length > 1e-6 else None


def observe_motion(scene):
    global angle_matches
    for person in scene.entities:
        if person.kind != 'person' or len(person.pose) != 33 or person.track_id not in app.output_canvas._poses:
            continue
        if not all(person.pose[i].confidence > .65 for i in (11, 12, 23, 24)):
            continue
        target = app.output_canvas._poses[person.track_id][0]
        for parent, child in ((11, 13), (13, 15), (12, 14), (14, 16),
                              (23, 25), (25, 27), (24, 26), (26, 28)):
            pa, pb = person.pose[parent], person.pose[child]
            if min(pa.confidence, pb.confidence) < .8:
                continue
            raw_a, raw_b = (pa.x * 1280, pa.y * 720), (pb.x * 1280, pb.y * 720)
            if math.dist(raw_a, raw_b) < 20:
                continue
            observed = direction(raw_a, raw_b)
            rendered = direction(target[parent], target[child])
            if not observed or not rendered:
                continue
            agreement = observed[0] * rendered[0] + observed[1] * rendered[1]
            # Reliable actual input/output bone directions should agree;
            # fallback actors are excluded from this evidence count.
            if agreement > .98:
                angle_matches += 1
                key = (person.track_id, parent, child)
                prior = previous_bones.get(key)
                if prior and math.dist(prior[0], observed) > .025 and math.dist(prior[1], rendered) > .025:
                    motion_tracks.add(person.track_id)
                previous_bones[key] = (observed, rendered)


def poll():
    global state, playing_from, last_sample
    try:
        assert time.perf_counter() - started < 90, (state, app.video_position, app.ai_status_var.get())
        if state == 'initial_paused':
            if not ready():
                app.after(50, poll)
                return
            # A preloaded still starts in STOPPED; both states freeze the
            # source timestamp without starting playback.
            assert app.state_value in (RunState.STOPPED, RunState.PAUSED)
            original = render()
            assert not app.output_canvas.find_withtag('skeleton-person')
            fixed = {key: tuple(value[0]) for key, value in app.output_canvas._poses.items()}
            bound = toggle(True)
            assert bound.skeleton_binding
            assert app.output_canvas.find_withtag('skeleton-person'), 'No reliable actual pose was bound at the paused sample'
            changed = []
            for person in bound.entities:
                ident = person.track_id
                if ident in fixed and ident in app.output_canvas._poses:
                    actual = tuple(app.output_canvas._poses[ident][0])
                    delta = max(math.dist(a[:2], b[:2]) for a, b in zip(fixed[ident], actual))
                    if delta > 2:
                        changed.append(ident)
                        paused_samples.append(dict(track_id=ident, action=person.action,
                            observed=[(p.x, p.y, p.confidence) for p in person.pose],
                            preset=fixed[ident], bound=actual, maximum_difference_px=delta))
            assert changed, 'Binding made no observable joint change on the same real sample'
            photos = tuple(app.output_canvas._images)
            app.output_canvas.draw(bound, simulated=False)
            assert all(a is b for a, b in zip(photos, app.output_canvas._images)), 'Unchanged skeleton misses its sprite cache'
            record(state, changed_people=changed)
            playing_from = app.video_position
            app.start()
            state = 'playing_bound'
        elif state == 'playing_bound':
            if ready():
                sample = (app.detection_result.generation, app.detection_result.timestamp)
                if sample != last_sample:
                    last_sample = sample
                    input_times.add(sample)
                    presented = render()
                    if app.output_canvas.find_withtag('skeleton-person'):
                        observe_motion(presented)
            if app.video_position - playing_from >= 4:
                assert len(input_times) >= 3, 'Too few actual pose samples during playback'
                assert motion_tracks, 'No track showed corresponding observed/output bone-angle changes'
                assert angle_matches >= 5, 'Insufficient actual bone-direction agreement'
                record(state, input_updates=len(input_times), moving_tracks=sorted(motion_tracks))
                app.pause()
                state = 'paused_again'
        elif state == 'paused_again':
            if not ready():
                app.after(50, poll)
                return
            toggle(False)
            assert not app.output_canvas.find_withtag('skeleton-person')
            assert app.output_canvas.find_withtag('preset-object')
            toggle(True)
            app.person_action_var.set('抬手')
            manual = render()
            assert all(e.action_manual and not e.pose for e in manual.entities if e.kind == 'person')
            assert not app.output_canvas.find_withtag('skeleton-person')
            app.person_action_var.set('自动姿态')
            render()
            record(state)
            old_generation = app.video.generation
            app.seek_video(37.)
            assert app.video.generation > old_generation
            assert app.scene is None and app.detection_result is None
            state = 'after_seek'
        elif state == 'after_seek':
            # This destination legitimately contains no detected people.
            # A new current detection result, including an empty result,
            # is enough to prove that the old generation was discarded.
            if not (app.scene and app.video_frame and app._detection_is_current()):
                app.after(50, poll)
                return
            assert abs(app.detection_result.timestamp - 37.) < .2
            assert app.detection_result.generation == app.video.generation
            presented = render()
            assert presented.skeleton_binding and presented.frame_clipping
            if not presented.entities:
                assert not app.output_canvas.find_withtag('skeleton-person')
                assert not app.output_canvas.find_withtag('preset-object')
            record(state)
            app.stop()
            assert app.scene is None and app.detection_result is None
            state = 'stopped'
        elif state == 'stopped':
            assert app._presentation_scene(None) is None
            assert not app.output_canvas.find_withtag('skeleton-person')
            assert not app.output_canvas.find_withtag('preset-object')
            report = dict(passed=True, source=str(source), records=records,
                input_updates=len(input_times), moving_tracks=sorted(motion_tracks),
                reliable_bone_direction_matches=angle_matches, paused_samples=paused_samples,
                checks=['same real paused sample changes output joints when binding is enabled',
                        'switch uses existing pose without resubmitting detection',
                        'unchanged skeleton reuses sprite cache',
                        'real playback changes observed and output angles on the same tracks',
                        'disabling restores preset rendering', 'manual actions override binding',
                        'Boolean setting roundtrip', 'seek rejects old detection generation',
                        'stop removes output actors'])
            (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k, v in report.items() if k != 'paused_samples'}, ensure_ascii=False), flush=True)
            app.settings_path = saved_settings
            app.close()
            return
        app.after(50, poll)
    except Exception:
        app._smoke_failure()


app.after(100, poll)
app.mainloop()
sys.exit(int(app.test_failed))
