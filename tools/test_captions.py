from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.core import Scene,Entity,TextRegion
from stickfigure.captions import ActionCaptions
from stickfigure.rendering import SceneCanvas

class CaptionChecks(unittest.TestCase):
    def setUp(self):
        self.captions=ActionCaptions();self.actor=Entity('p','person',.5,.9,action='PHONE_LOOK',bbox=(.4,.2,.6,.9))
    def scene(self,t=0,**kwargs):return Scene(0,0,1,t,(replace(self.actor,**kwargs),),frame_clipping=True)
    def test_phone_label_expires_after_two_seconds_without_retrigger(self):
        for t,text in ((0,'玩手机'),(1.99,'玩手机'),(2,''),(3,'')):
            self.assertEqual(self.captions.apply(self.scene(t)).entities[0].action_caption,text)
    def test_change_refreshes_label_and_idle_does_not_create_label(self):
        self.captions.apply(self.scene())
        self.assertEqual(self.captions.apply(self.scene(1,action='DOWN')).entities[0].action_caption,'倒地')
        self.assertEqual(self.captions.apply(self.scene(2.9,action='DOWN')).entities[0].action_caption,'倒地')
        self.assertEqual(self.captions.apply(self.scene(3.1,action='IDLE')).entities[0].action_caption,'')
    def test_fire_short_pose_keeps_change_notice_for_two_seconds(self):
        self.assertEqual(self.captions.apply(self.scene(action='GUN_FIRE')).entities[0].action_caption,'开枪')
        self.assertEqual(self.captions.apply(self.scene(.3,action='GUN_HOLD')).entities[0].action_caption,'开枪')
        self.assertEqual(self.captions.apply(self.scene(2.1,action='GUN_HOLD')).entities[0].action_caption,'')
    def test_missing_prediction_toggle_and_manual_origin(self):
        self.assertEqual(self.captions.apply(self.scene(action_manual=True)).entities[0].action_caption,'手动·玩手机')
        self.assertEqual(self.captions.apply(self.scene(.2,predicted=True)).entities[0].action_caption,'')
        self.assertFalse(self.captions.tracks)
        self.assertEqual(self.captions.apply(self.scene(.3),enabled=False).entities[0].action_caption,'')
        self.captions.apply(replace(self.scene(.4),entities=()));self.assertFalse(self.captions.tracks)
    def test_seek_epoch_and_pause(self):
        self.captions.apply(self.scene())
        self.assertEqual(self.captions.apply(self.scene()).entities[0].action_caption,'玩手机')
        self.captions.apply(self.scene(4))
        self.assertEqual(self.captions.apply(self.scene(.1)).entities[0].action_caption,'玩手机')
        self.assertEqual(self.captions.apply(replace(self.scene(4),scene_epoch=2)).entities[0].action_caption,'玩手机')
    def test_decoder_generation_change_preserves_pause_notice_timer(self):
        scene=self.scene()
        self.captions.apply(scene,scope=('video',7))
        self.assertEqual(self.captions.apply(replace(scene,animation_time=3),scope=('video',7)).entities[0].action_caption,'')
        self.assertEqual(self.captions.apply(replace(scene,scene_epoch=2000007,animation_time=3),scope=('video',7)).entities[0].action_caption,'')
        self.assertEqual(self.captions.apply(replace(scene,scene_epoch=2000008,animation_time=3),scope=('video',8)).entities[0].action_caption,'玩手机')
    def test_native_text_ocr_independence_clipping_and_cached_actor(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            scene=self.captions.apply(self.scene());scene=replace(scene,texts=(TextRegion('原画面文字',1,(.1,.8,.3,.9)),))
            canvas.draw(scene)
            ids=canvas.find_withtag('action-caption');self.assertEqual(len(ids),1)
            self.assertEqual(canvas.itemcget(ids[0],'text'),'玩手机')
            self.assertEqual(canvas.itemcget(canvas.find_withtag('ocr-text')[0],'text'),'原画面文字')
            canvas.draw(scene);self.assertEqual(len(canvas.find_withtag('action-caption')),1)
            actor=replace(scene.entities[0],bbox=(-.1,-.1,.1,.5))
            canvas.draw(replace(scene,entities=(actor,)))
            box=canvas.coords(canvas.find_withtag('action-caption-background')[0]);self.assertTrue(0<=box[0]<box[2]<=640 and 0<=box[1]<box[3]<=360)
            canvas.draw(replace(scene,entities=(replace(actor,predicted=True),)))
            self.assertFalse(canvas.find_withtag('action-caption'))
        finally:root.destroy()

if __name__=='__main__':unittest.main()
