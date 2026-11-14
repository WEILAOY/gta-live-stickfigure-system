from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.detection import Detection,ObjectHint,merge_down_proposals,unrotate_box,YoloXDetector
from stickfigure.tracking import TrackManager
from stickfigure.actions import classify_action,action_mirror,horizontal_posture
from stickfigure.assets import preset_pose,down_render_box,down_bounds
from stickfigure.core import Entity,Scene
from stickfigure.rendering import SceneCanvas
from stickfigure.shading import contact_shadow_boxes

class DownChecks(unittest.TestCase):
    def test_rotated_boxes_return_to_source_coordinates(self):
        original=(.2,.3,.7,.6)
        np.testing.assert_allclose(unrotate_box((.3,.3,.6,.8),1),original)
        np.testing.assert_allclose(unrotate_box((.4,.2,.7,.7),3),original)
        raw=unrotate_box((-.1,.2,.4,1.1),1)
        self.assertLess(raw[0],0);self.assertLess(raw[1],0)

    def test_cross_view_person_confirms_paused_frame_and_preserves_context(self):
        box=(.30,.50,.60,.70);normal=Detection('person',.40,box,object_hints=(ObjectHint('phone',.8,(.4,.5,.41,.51)),))
        rotated=Detection('person',.53,(.50,.40,.70,.70))
        result=merge_down_proposals((normal,),((rotated,1),),852,480)
        self.assertEqual(len(result),1);d=result[0]
        self.assertEqual(d.box,normal.box);self.assertEqual(d.confidence,normal.confidence)
        self.assertEqual(d.object_hints,normal.object_hints);self.assertEqual(d.posture_hint,'DOWN');self.assertTrue(d.corroborated)
        self.assertTrue(TrackManager().update(result,0)[0].confirmed)
        self.assertFalse(TrackManager().update((normal,),0)[0].confirmed)
        self.assertEqual(merge_down_proposals((normal,),(),852,480),(normal,))

    def test_unsupported_weak_or_vertical_proposals_are_not_drawable_floor_people(self):
        wide=Detection('person',.53,(.50,.40,.70,.70))
        self.assertFalse(merge_down_proposals((),((wide,1),),852,480))
        self.assertFalse(merge_down_proposals((),((replace(wide,confidence=.9,box=(.1,.2,.8,.3)),1),),852,480))
        high=merge_down_proposals((),((replace(wide,confidence=.8),1),),852,480)
        self.assertEqual(len(high),1);self.assertFalse(high[0].corroborated)
        self.assertEqual(high[0].posture_hint,'DOWN')

    def test_horizontal_pose_selects_down_and_sitting_stays_sitting(self):
        for mirror in (False,True):
            pose=preset_pose('DOWN',mirror=mirror)
            self.assertTrue(horizontal_posture(pose));self.assertEqual(classify_action(pose),'DOWN')
            self.assertEqual(action_mirror(pose,'DOWN'),mirror)
        self.assertNotEqual(classify_action(preset_pose('SIT')),'DOWN')
        self.assertNotEqual(classify_action(preset_pose('CROUCH')),'DOWN')
        poor=tuple(replace(p,confidence=.1) if i in (27,28) else p for i,p in enumerate(preset_pose('DOWN')))
        self.assertFalse(horizontal_posture(poor))

    def test_fitted_down_geometry_uses_horizontal_extent_without_standing_height(self):
        for mirror in (False,True):
            extent=(300,300,480,370);a,b,c,d=down_render_box(extent,mirror);u,v,x,y=down_bounds(mirror)
            self.assertLessEqual(c-a,250)
            self.assertGreaterEqual(a+u*(c-a),extent[0]-.01)
            self.assertLessEqual(a+x*(c-a),extent[2]+.01)
            self.assertGreaterEqual(b+v*(d-b),extent[1]-.01)
            self.assertAlmostEqual(b+y*(d-b),extent[3])
        e=Entity('down','person',.5,.7,bbox=(.3,.5,.7,.7),action='DOWN',posture_fit=True)
        shadow=contact_shadow_boxes((e,))[0]
        self.assertAlmostEqual((shadow[0]+shadow[2])/2,.5)

    def test_eight_people_are_not_truncated_to_four(self):
        detector=YoloXDetector.__new__(YoloXDetector);detector.np=np;detector.cv2=cv2
        detector.width=detector.height=256;detector.grid=np.zeros((6,2),np.float32);detector.strides=np.ones((6,1),np.float32);detector.input_name='input'
        output=np.zeros((1,6,85),np.float32)
        for i in range(6):output[0,i,:5]=(15+i*40,128,np.log(18),np.log(90),1);output[0,i,5]=.9
        class Session:
            def run(self,*args):return [output]
        detector.session=Session();people,*_=detector.detect_rgb(bytes(256*256*3),256,256)
        self.assertEqual(len(people),6)

    def test_actual_down_renderer_remains_inside_extent_and_clips_only_viewport(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            for mirror in (False,True):
                for box in ((.35,.5,.65,.7),(-.1,.5,.2,.7),(.8,.5,1.1,.7),(.3,-.1,.7,.08),(.3,.94,.7,1.08)):
                    actor=Entity('floor','person',.5,.7,bbox=box,action='DOWN',posture_fit=True,action_mirror=mirror)
                    scene=Scene(0,0,1,0,(actor,),frame_clipping=True)
                    canvas.draw(scene);self.assertTrue(canvas.find_withtag('preset-object'))
                    for photo,bounds in canvas._layer_cache.values():
                        if photo:self.assertTrue(0<=bounds[0]<bounds[2]<=640 and 0<=bounds[1]<bounds[3]<=360)
                    if box[0]>.3 and box[2]<.7:
                        self.assertLessEqual(canvas._images[0].width(),round((box[2]-box[0])*640)+12)
                        self.assertLessEqual(canvas._images[0].height(),round((box[3]-box[1])*360)+12)
                    canvas.draw(replace(scene,entities=(replace(actor,predicted=True),)))
                    self.assertFalse(canvas.find_withtag('preset-object'))
        finally:root.destroy()

if __name__=='__main__':unittest.main()
