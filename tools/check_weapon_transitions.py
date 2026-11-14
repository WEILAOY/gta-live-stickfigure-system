"""Exercise firearm state changes with the supplied video, not synthetic shots."""
from pathlib import Path
import json, sys, time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application

base = Path(__file__).resolve().parents[1]
proof = base.parent / '25_持枪与开火恢复验证'
source = json.loads((base.parent / '03_测试素材/gta6-source.json').read_text(encoding='utf-8'))['source']

class CheckApp(Application):
    def _run_smoke(self): pass

app = CheckApp(base, smoke_test=True, initial_video=source, initial_position=846.8)
app.ai_var.set(True)
app.person_action_var.set('自动姿态')
app.auto_weapon_var.set(True)
app.hud_assist_var.set(True)
app.auto_fire_var.set(True)
app._hud_changed()
stage = 'ready'
began = time.perf_counter()
records = []
seen_hold = False
seen_pistol = False
seen_pistol_fire = False

def actors():
    scene = app._presentation_scene(app.scene)
    return [e for e in scene.entities if e.kind == 'person' and not e.predicted] if scene else []

def advance(name):
    global stage, began
    records.append(dict(stage=stage, position=app.video_position, passed=True))
    print(records[-1], flush=True)
    stage = name
    began = time.perf_counter()

def poll():
    global seen_hold, seen_pistol, seen_pistol_fire
    try:
        assert time.perf_counter() - began < 60, (stage, app.video_position, app.ai_status_var.get())
        if stage == 'ready':
            if app.video_frame and app._detection_is_current():
                app.start(); advance('rifle')
        elif stage == 'rifle':
            if app.video_position >= 849 and app._shot_count > 0:
                app.pause(); advance('paused')
        elif stage == 'paused':
            if time.perf_counter() - began > .8:
                assert abs(app.video_position - records[-1]['position']) < .04
                app.auto_fire_var.set(False); app._auto_fire_changed()
                assert not app._shot_effects and not app._unshown_shots
                app.start(); advance('disabled')
        elif stage == 'disabled':
            current = actors()
            assert not any(e.action == 'GUN_FIRE' for e in current)
            assert app._shot_count == 0 and not app._shot_effects
            seen_hold |= any(e.aim_point is not None for e in current)
            if app.video_position >= 852:
                assert seen_hold, 'Disabling flashes also removed observed holding'
                advance('burning_after_seek')
                app.seek_video(959)
                assert not app._shot_effects and not app.fire_detector.holds
        elif stage == 'burning_after_seek':
            assert not any(e.aim_point is not None for e in actors())
            if app.video_position >= 963:
                advance('pistol_after_seek')
                app.auto_fire_var.set(True); app._auto_fire_changed()
                app.seek_video(1403.5)
                assert not app._shot_effects and not app._unshown_shots
        elif stage == 'pistol_after_seek':
            current = actors()
            seen_pistol |= any(e.weapon == 'pistol' and e.aim_point is not None for e in current)
            seen_pistol_fire |= any(e.weapon == 'pistol' and e.action == 'GUN_FIRE' for e in current)
            if app.video_position >= 1408 and app._shot_count > 0:
                assert seen_pistol and seen_pistol_fire, 'No pistol holding/firing after seek'
                advance('stopped')
                app.stop()
                assert app.scene is None and not app._shot_effects and not app._unshown_shots
                assert not app.fire_detector.holds
                proof.mkdir(exist_ok=True)
                (proof / 'weapon-state-transitions-result.json').write_text(json.dumps(dict(
                    passed=True, records=records, checks=[
                        'Pause freezes video position',
                        'Disabling automatic flashes clears firing but preserves observed holding',
                        'Seeking from armed footage to burning footage leaves no old gun',
                        'Re-enabling and seeking restores pistol firing',
                        'Stop clears actors, held weapons and pending flashes']), ensure_ascii=False, indent=2), encoding='utf-8')
                app.close(); return
        app.after(40, poll)
    except Exception:
        app._smoke_failure()

app.after(150, poll)
app.mainloop()
sys.exit(1 if app.test_failed else 0)
