"""Color-mode presentation, cache, settings and cancellation without models."""
from pathlib import Path
import sys,json,tempfile,threading,queue,unittest,tkinter as tk
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.app import Application,SOURCES
from stickfigure.core import Scene,Entity,ShadeRegion,ColorRegion,RoadGeometry,RunState
from stickfigure.road import RoadResult,RoadWorker
from stickfigure.rendering import SceneCanvas
from stickfigure.video import VideoFrame
from stickfigure.detection import DetectionResult

BASE=Path(__file__).resolve().parents[1]
FULL=((0.,0.),(1.,0.),(1.,1.),(0.,1.))
COLORS=(ColorRegion('#d5e6d0',FULL),)
SHADES=(ShadeRegion(0,FULL),)


class ColorRendererChecks(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.canvas=SceneCanvas(self.root,width=640,height=360)
        self.canvas.pack();self.root.update()
        self.actor=Entity('person','person',.5,.8,bbox=(.43,.2,.57,.8))
        self.scene=Scene(0,0,1,0,(self.actor,),False,frame_clipping=True)
    def tearDown(self):self.root.destroy()

    def test_background_color_cache_and_comic_switch_keep_actor_material(self):
        colored=replace(self.scene,colors=COLORS)
        self.canvas.draw(colored)
        background=self.canvas._background_cache[1];actor=self.canvas._images[0]
        self.assertTrue(self.canvas.find_withtag('color-background'))
        self.assertFalse(self.canvas.find_withtag('comic-background'))
        self.assertEqual(background.get(10,10),(213,230,208))
        self.canvas.draw(colored)
        self.assertIs(self.canvas._background_cache[1],background)
        self.assertIs(self.canvas._images[0],actor)
        self.canvas.draw(replace(colored,colors=(ColorRegion('#d4e4f1',FULL),)))
        self.assertIsNot(self.canvas._background_cache[1],background)
        self.assertEqual(self.canvas._background_cache[1].get(10,10),(212,228,241))
        self.assertIs(self.canvas._images[0],actor)
        self.canvas.draw(replace(self.scene,shading=SHADES))
        self.assertTrue(self.canvas.find_withtag('comic-background'))
        self.assertFalse(self.canvas.find_withtag('color-background'))
        self.assertIs(self.canvas._images[0],actor)  # same preset and white edge
        self.canvas.draw(self.scene)
        self.assertFalse(self.canvas.find_withtag('color-background'))
        self.assertFalse(self.canvas.find_withtag('comic-background'))

    def test_colored_background_preserves_frame_clipping_and_no_ghosts(self):
        car=Entity('car','car',.5,.8,bbox=(.3,.4,.7,.8),yaw=90)
        for box in ((-.2,.3,.2,.8),(.8,.3,1.2,.8),(.3,-.2,.7,.2),(.3,.8,.7,1.2)):
            self.canvas.draw(replace(self.scene,entities=(replace(car,bbox=box),),colors=COLORS))
            self.assertTrue(self.canvas.find_withtag('preset-object'))
            for photo,bounds in self.canvas._layer_cache.values():
                if photo:self.assertTrue(0<=bounds[0]<bounds[2]<=640 and 0<=bounds[1]<bounds[3]<=360)
        self.canvas.draw(replace(self.scene,entities=(replace(car,predicted=True),),colors=COLORS))
        self.assertTrue(self.canvas.find_withtag('color-background'))
        self.assertFalse(self.canvas.find_withtag('preset-object'))
        self.assertFalse(self.canvas.hitboxes)


class ColorApplicationChecks(unittest.TestCase):
    def setUp(self):
        class App(Application):
            def _run_smoke(self):pass
        self.app=App(BASE,smoke_test=True)
        self.folder=tempfile.TemporaryDirectory(dir=BASE/'runtime/smoke')
        self.app.settings_path=Path(self.folder.name)/'settings.json'
        # Manually injected frames must never start a neural worker in unit tests.
        self.submit=patch.object(self.app.road_worker,'submit');self.submit.start()
        self.preview=patch.object(self.app,'_draw_video');self.preview.start()
    def tearDown(self):
        self.preview.stop();self.submit.stop()
        for ident in self.app.tk.call('after','info'):self.app.after_cancel(ident)
        self.app.close();self.folder.cleanup()

    def current_scene(self):
        a=self.app;a.source_var.set(SOURCES[2]);a.state_value=RunState.PAUSED
        a.video_position=0.;a.video_frame=VideoFrame(a.video.generation,0.,160,90,b'\0'*(160*90*3))
        a.scene=Scene(0,0,1,0,(Entity('person','person',.5,.8,bbox=(.43,.2,.57,.8)),),False)
        a.road_result=RoadResult(a.road_worker.epoch,a.video.generation,0.,RoadGeometry(),1,
                                 shading=SHADES,colors=COLORS)
        return a.scene

    def test_toggle_preserves_shadow_choices_and_saves_boolean(self):
        a=self.app;a.shading_var.set(True);a.sky_var.set(True)
        a.shadow_mode_var.set('分区+投影');a.shadow_levels_var.set('4')
        a.shadow_density_var.set('密');a.shadow_detail_var.set('精细')
        before=(a.shading_var.get(),a.sky_var.get(),a.shadow_mode_var.get(),
                a.shadow_levels_var.get(),a.shadow_density_var.get(),a.shadow_detail_var.get())
        a.color_var.set(True);a._color_changed()
        self.assertTrue(a._load_settings()['color_enabled'])
        self.assertEqual(a._shadow_options(),(4,'精细',True))
        self.assertIn('disabled',a.shading_checkbox.state())
        self.assertIn('disabled',a.sky_checkbox.state())
        a.open_shadow_settings()
        self.assertTrue(all('disabled' in w.state() for w in a._shadow_setting_controls))
        a.color_var.set(False);a._color_changed()
        self.assertFalse(a._load_settings()['color_enabled'])
        self.assertNotIn('disabled',a.shading_checkbox.state())
        self.assertNotIn('disabled',a.sky_checkbox.state())
        self.assertEqual(before,(a.shading_var.get(),a.sky_var.get(),a.shadow_mode_var.get(),
                                a.shadow_levels_var.get(),a.shadow_density_var.get(),a.shadow_detail_var.get()))

    def test_invalid_color_setting_is_ignored(self):
        a=self.app
        for value in ('true',1,[],None):
            a.settings_path.write_text(json.dumps({'color_enabled':value}),encoding='utf-8')
            self.assertNotIn('color_enabled',a._load_settings())
        a.settings_path.write_text('{"color_enabled": true}',encoding='utf-8')
        self.assertIs(a._load_settings()['color_enabled'],True)

    def test_color_alone_enables_environment_analysis(self):
        a=self.app
        for value in (a.road_var,a.buildings_var,a.sky_var,a.shading_var,a.color_var):value.set(False)
        self.assertFalse(a._environment_enabled())
        a.color_var.set(True)
        self.assertTrue(a._environment_enabled())

    def test_pause_generation_switch_does_not_consume_new_frames_cadence(self):
        a=self.app;a.ai_var.set(False);a.text_var.set(False);a.shading_var.set(True)
        for colored in (True,False):
            with self.subTest(colored=colored):
                self.current_scene();a.road_worker.submit.reset_mock()
                old_frame=a.video_frame
                # A pause request advances the decoder generation before its new
                # single paused frame arrives; the previous display frame still exists.
                a.video.cancel()
                self.assertNotEqual(old_frame.generation,a.video.generation)
                a.color_var.set(colored);a._color_changed()
                a.road_worker.submit.assert_not_called()
                self.assertIsNone(a.road_cadence.previous)
                self.assertIsNone(a.road_cadence.next_due)
                self.assertEqual(a._last_road_submit,float('-inf'))
                a.video.frames.put(old_frame);a._poll_video()
                a.road_worker.submit.assert_not_called()
                self.assertIsNone(a.road_cadence.next_due)
                new_frame=replace(old_frame,generation=a.video.generation)
                a.video.frames.put(new_frame);a._poll_video()
                a.road_worker.submit.assert_called_once()
                self.assertIs(a.road_worker.submit.call_args.args[0],new_frame)
                self.assertEqual(a.road_worker.submit.call_args.args[2][2],colored)
                self.assertEqual(a._last_road_submit,new_frame.timestamp)
                self.assertIsNotNone(a.road_cadence.next_due)
                a.video.frames.put(new_frame);a._poll_video()
                a.road_worker.submit.assert_called_once()  # no duplicate same-time work

    def test_old_generation_scene_cut_cannot_resubmit_previous_frame(self):
        a=self.app;self.current_scene();a.ai_var.set(True);a.color_var.set(True)
        a._last_scene_revision=1
        old_frame=a.video_frame
        a.video.cancel();a._reset_road()
        epoch=a.road_worker.epoch
        result=DetectionResult(a.detector.epoch,old_frame.generation,old_frame.timestamp,
                               (),1.,1.,'CPU',scene_revision=2)
        a.detector.results.put(result);a._poll_detection()
        a.road_worker.submit.assert_not_called()
        self.assertEqual(a.road_worker.epoch,epoch)
        self.assertEqual(a._last_scene_revision,1)
        self.assertIsNone(a.road_cadence.previous)
        self.assertIsNone(a.road_cadence.next_due)

    def test_color_replaces_shading_and_contact_then_restores_them(self):
        a=self.app;a.shading_var.set(True);a.sky_var.set(True);a.shadow_mode_var.set('分区+投影')
        raw=self.current_scene();a.color_var.set(True)
        colored=a._presentation_scene(raw)
        self.assertEqual(colored.colors,COLORS)
        self.assertIsNone(colored.shading);self.assertFalse(colored.contact_shadows)
        a.color_var.set(False);gray=a._presentation_scene(raw)
        self.assertIsNone(gray.colors);self.assertEqual(gray.shading,SHADES)
        self.assertTrue(gray.contact_shadows)
        self.assertEqual(colored.entities,gray.entities)

    def test_switch_and_generation_reject_late_color_results(self):
        a=self.app;raw=self.current_scene();old=a.road_result
        a.color_var.set(True);a._color_changed()
        self.assertGreater(a.road_worker.epoch,old.epoch)
        self.assertIsNone(a.road_result)
        a.road_worker.results.put(old);a._poll_road()
        self.assertIsNone(a.road_result)
        self.assertIsNone(a._presentation_scene(raw).colors)
        current=replace(old,epoch=a.road_worker.epoch)
        a.road_worker.results.put(current);a._poll_road()
        self.assertEqual(a._presentation_scene(raw).colors,COLORS)
        a.road_result=replace(current,generation=a.video.generation+1)
        self.assertIsNone(a._presentation_scene(raw).colors)
        a.road_result=replace(current,timestamp=-10)
        self.assertIsNone(a._presentation_scene(raw).colors)


class ColorWorkerChecks(unittest.TestCase):
    def test_switch_during_analysis_discards_old_colored_result(self):
        entered=threading.Event();release=threading.Event();calls=[]
        class SlowSegmenter:
            def __init__(self,path):self.colors=None;self.shading=None
            def reset(self):self.colors=None;self.shading=None
            def segment(self,frame):
                color=self.shading_options[2];calls.append(color)
                if len(calls)==1:entered.set();self.waited=release.wait(3)
                self.colors=COLORS if color else None;self.shading=None if color else SHADES
                return RoadGeometry(),1
        with patch('stickfigure.road.RoadSegmenter',SlowSegmenter):
            worker=RoadWorker('unused')
            try:
                worker.submit(VideoFrame(1,0,1,1,b'\0\0\0'),shading_options=(6,'标准',True))
                self.assertTrue(entered.wait(2));worker.reset()
                worker.submit(VideoFrame(1,.1,1,1,b'\0\0\0'),shading_options=(6,'标准',False))
                release.set();result=worker.results.get(timeout=3)
                self.assertEqual(result.epoch,worker.epoch)
                self.assertIsNone(result.colors);self.assertEqual(result.shading,SHADES)
                self.assertEqual(calls,[True,False])
                with self.assertRaises(queue.Empty):worker.results.get(timeout=.1)
            finally:release.set();worker.close();worker._thread.join(3)


if __name__=='__main__':unittest.main()
