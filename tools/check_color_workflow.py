"""Real-video color toggle, pause/play, shadow restoration and seek cleanup."""
from pathlib import Path
import sys,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application
from stickfigure.core import RunState

base=Path(__file__).resolve().parents[1]
out=base.parent.parent/'color-workflow';out.mkdir(parents=True,exist_ok=True)
source=base.parent/'03_测试素材/gta5_test_01.mp4'

class TestApp(Application):
    def _run_smoke(self):pass

app=TestApp(base,smoke_test=True,initial_video=str(source),initial_position=90)
app.ai_var.set(True);app.shading_var.set(True);app.sky_var.set(True)
app.road_var.set(True);app.buildings_var.set(True);app.color_var.set(False)
app.shadow_mode_var.set('分区+投影');app.shadow_levels_var.set('6')
app.shadow_density_var.set('中等');app.shadow_detail_var.set('标准')
app._road_changed()
state='gray_paused';started=time.perf_counter();started_color=None;paused_position=None
records=[];color_timestamps=set();saved=app.settings_path
app.settings_path=out/'settings.json'

def record(label):
    records.append(dict(stage=label,position=app.video_position,epoch=app.road_worker.epoch))

def presented():
    scene=app._presentation_scene(app.scene)
    if scene is not None:app.output_canvas.draw(scene,simulated=False)
    return scene

def poll():
    global state,started_color,paused_position
    try:
        assert time.perf_counter()-started<80,(state,app.video_position,app.road_status_var.get())
        if state=='gray_paused':
            if not (app._environment_is_current() and app.scene and app.output_canvas.winfo_width()>100):
                app.after(50,poll);return
            scene=presented();assert scene.shading is not None and scene.colors is None
            assert app.output_canvas.find_withtag('comic-background')
            paused_position=app.video_position;old=app.road_worker.epoch
            record(state);app.color_var.set(True);app._color_changed()
            assert app.road_worker.epoch>old and app.road_result is None
            assert app._load_settings()['color_enabled'] is True
            state='color_paused'
        elif state=='color_paused':
            if not (app._environment_is_current() and app.road_result.colors):
                app.after(50,poll);return
            scene=presented();assert scene.colors and scene.shading is None and not scene.contact_shadows
            assert app.output_canvas.find_withtag('color-background')
            assert not app.output_canvas.find_withtag('comic-background')
            assert not app.output_canvas.find_withtag('contact-shadow')
            assert abs(app.video_position-paused_position)<.05
            before=app.output_canvas._background_cache[1]
            presented();assert app.output_canvas._background_cache[1] is before
            record(state);app.start();started_color=app.video_position;state='color_playing'
        elif state=='color_playing':
            if app._environment_is_current() and app.road_result.colors:
                color_timestamps.add(app.road_result.timestamp)
            if app.video_position-started_color>=3:
                assert len(color_timestamps)>=2,'Color background did not refresh during playback'
                assert app.output_canvas.find_withtag('color-background')
                app.pause();paused_position=app.video_position;record(state)
                app.color_var.set(False);app._color_changed()
                assert app._load_settings()['color_enabled'] is False
                assert app.shading_var.get() and app.sky_var.get() and app.shadow_mode_var.get()=='分区+投影'
                state='gray_restored'
        elif state=='gray_restored':
            if not (app._environment_is_current() and app.road_result.shading):
                app.after(50,poll);return
            scene=presented();assert scene.colors is None and scene.shading is not None and scene.contact_shadows
            assert app.output_canvas.find_withtag('comic-background')
            assert not app.output_canvas.find_withtag('color-background')
            assert abs(app.video_position-paused_position)<.05
            record(state);app.color_var.set(True);app._color_changed();state='color_before_seek'
        elif state=='color_before_seek':
            if not (app._environment_is_current() and app.road_result.colors):
                app.after(50,poll);return
            record(state);old=app.road_worker.epoch;app.seek_video(35)
            assert app.road_worker.epoch>old and app.road_result is None and app.scene is None
            state='color_after_seek'
        elif state=='color_after_seek':
            if not (app._environment_is_current() and app.road_result.colors and app.video_frame):
                app.after(50,poll);return
            assert abs(app.road_result.timestamp-35)<1
            scene=presented();assert scene.colors and scene.shading is None
            record(state);app.stop()
            assert app.road_result is None and app.scene is None
            assert app._presentation_scene(None) is None
            report=dict(passed=True,source=str(source),color_updates=len(color_timestamps),records=records,
                        checks=['paused mode switch produces colors without advancing video',
                                'color mode replaces comic and contact layers',
                                'same color snapshot reuses raster cache',
                                'real playback refreshes colors',
                                'disabling colors restores original shadow options',
                                'toggle settings roundtrip','seek rejects old color results','stop clears output'])
            (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False),flush=True);app.settings_path=saved;app.close();return
        app.after(50,poll)
    except Exception:app._smoke_failure()

app.after(100,poll);app.mainloop();sys.exit(int(app.test_failed))
