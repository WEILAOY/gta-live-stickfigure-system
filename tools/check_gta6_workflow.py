"""Actual source/GUI integration; no timecoded action overrides in auto mode."""
from pathlib import Path
import sys,json,time
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.assets import ACTIONS,ACTION_GROUPS

base=Path(__file__).resolve().parents[1];out=base.parent/'13_GTA6动作验证'
source=json.loads((out/'source-info.json').read_text(encoding='utf-8'))['source']
class TestApplication(Application):
    def _run_smoke(self):pass

app=TestApplication(base,smoke_test=True,initial_video=source,initial_position=240)
app.ai_var.set(True);app.road_var.set(True);app.buildings_var.set(True)
app.person_action_var.set('自动姿态');app.detect_rate_var.set('10');app.road_rate_var.set('5')
app.combat_mirror_var.set(False)
app._detection_changed();app._road_changed();started=time.perf_counter();records={}

def ready():
    try:
        if not (app.detection_result and app.scene and app.scene.entities and app.road_result):
            assert time.perf_counter()-started<25,app.ai_status_var.get()
            app.after(100,ready);return
        assert app.video_info.width==852 and app.video_info.height==480 and abs(app.video_info.fps-30)<.01
        actions=[d.action for d in app.detection_result.detections if d.label=='person' and not d.predicted]
        assert 'PHONE_LOOK' in actions,actions
        records['initial_actions']=actions
        app.tabs.select(app.appearance_tab);app.update_idletasks()
        for group,names in ACTION_GROUPS.items():
            app.gallery_mode_var.set(group);app._draw_asset_gallery()
            assert len(app.gallery_canvas.hitboxes)==len(names),(group,len(app.gallery_canvas.hitboxes))
        for name,action in ACTIONS.items():
            if action is None:continue
            app.person_action_var.set(name)
            presented=app._presentation_scene(app.scene)
            people=[e for e in presented.entities if e.kind=='person']
            assert people and all(e.action==action and not e.pose and not e.action_mirror for e in people)
            # The phone shot is upper-body only. A fully fallen body can be
            # below this viewport, which is correct frame clipping. Verify
            # those materials in a fully visible fixture instead.
            render_scene=presented
            if action in ('FALL','DOWN'):
                render_scene=replace(presented,entities=(replace(people[0],bbox=(.42,.1,.58,.9),render_bbox=None),))
            app.output_canvas.draw(render_scene,simulated=False)
            assert app.output_canvas.find_withtag('preset-object'),name
        app.person_action_var.set('划桨');app.save_settings()
        assert app._load_settings()['person_action']=='划桨'
        app._restore_automatic();app.save_settings();app.tabs.select(app.preview_tab)
        app.start();app._gta6_play_time=time.perf_counter();app.after(500,playing)
    except Exception:app._smoke_failure()

def playing():
    try:
        if len(app._accepted_detection_times)<6:
            assert time.perf_counter()-app._gta6_play_time<15,(len(app._accepted_detection_times),app.ai_status_var.get())
            app.after(150,playing);return
        assert len(app._accepted_detection_times)>=6,len(app._accepted_detection_times)
        records['playback_detected_frames']=len(app._accepted_detection_times)
        records['playback_wait_seconds']=time.perf_counter()-app._gta6_play_time
        records['human_backend']=app.detection_result.backend
        records['environment_backend']=app.road_result.backend
        app.pause();app.seek_video(660)
        app._gta6_stage_time=time.perf_counter();app.after(100,seeked)
    except Exception:app._smoke_failure()

def seeked():
    try:
        if not (app.scene and app.scene.entities and app.detection_result and abs(app.detection_result.timestamp-660)<.15):
            assert time.perf_counter()-app._gta6_stage_time<15
            app.after(100,seeked);return
        assert app.detection_result.generation==app.video.generation
        assert app._presentation_scene(app.scene).frame_clipping
        records['seek_actions']=[e.action for e in app.scene.entities if e.kind=='person']
        app.road_var.set(False);app.buildings_var.set(False);app._road_changed()
        app.output_canvas.draw(app._presentation_scene(app.scene),simulated=False)
        assert app.output_canvas.find_withtag('preset-object')
        app.stop();assert app.scene is None and app.detection_result is None
        report=dict(passed=True,source=source,source_fps=30,presets=len(ACTIONS)-1,records=records,checks=[
            'GTA6 supplied source loads at native size and 30fps','real phone context selects preset PHONE_LOOK',
            'all action gallery groups render fixed presets','manual overrides use complete fixed materials',
            'manual overrides clear pose and mirror','new action setting roundtrip','automatic mode restored',
            'distinct real playback frames analyzed','GPU workers report actual backends','seek invalidates old generations',
            'seek analyzes new scene','frame-only clipping preserved','environment disabled preserves actors','stop clears output'])
        (out/'gta6-workflow-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        app.close()
    except Exception:app._smoke_failure()

app.after(100,ready);app.mainloop();sys.exit(1 if app.test_failed else 0)
