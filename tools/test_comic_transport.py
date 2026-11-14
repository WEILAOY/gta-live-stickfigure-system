from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.assets import vehicle_drawing
from stickfigure.core import Entity,Scene,ShadeRegion
from stickfigure.rendering import SceneCanvas
from stickfigure.shading import comic_pixels,extract_shading,contact_shadow_boxes
from stickfigure.detection import YoloXDetector
from stickfigure.tracking import TrackManager

class ComicTransportChecks(unittest.TestCase):
    def test_vehicle_meshes_all_views_and_rotor_bounds(self):
        for material in ('motorcycle','helicopter'):
            drawings=[]
            for yaw in range(0,360,45):
                for pitch in (0,22,78):
                    for phase in (0,22.5,67.5):
                        art=vehicle_drawing(yaw,pitch,material,phase)
                        self.assertGreater(len(art.shapes),25)
                        self.assertTrue(all(-1e-8<=v<=1+1e-8 for s in art.shapes for v in s.points))
                        self.assertGreater(art.aspect,0)
                drawings.append(vehicle_drawing(yaw,22,material))
            self.assertEqual(len(set(drawings)),8)
        self.assertNotEqual(vehicle_drawing(45,22,'helicopter',0),vehicle_drawing(45,22,'helicopter',22.5))
        self.assertAlmostEqual(vehicle_drawing(45,22,'helicopter',0).aspect,vehicle_drawing(45,22,'helicopter',22.5).aspect)

    def test_comic_shades_keep_white_paper_and_never_solid_black(self):
        full=((0,0),(1,0),(1,1),(0,1))
        for tone in (0,1):
            image=comic_pixels((ShadeRegion(tone,full),),640,360)
            colors,counts=np.unique(image[:,:,:3].reshape(-1,3),axis=0,return_counts=True)
            self.assertEqual(len(colors),2)
            self.assertGreater(np.mean(np.all(image[:,:,:3]==255,axis=2)),.70)
            self.assertGreaterEqual(int(image[:,:,:3].min()),100)
            self.assertTrue(np.all(image[:,:,3]==255))
        dots=comic_pixels((ShadeRegion(1,full),),640,360)
        hatches=comic_pixels((ShadeRegion(0,full),),640,360)
        self.assertFalse(np.array_equal(dots,hatches))

    def test_sky_uses_semantic_evidence_and_preserves_building_hole(self):
        rgb=np.zeros((90,160,3),np.uint8)
        labels=np.full((90,160),10,np.uint8);labels[20:55,60:100]=2
        regions=extract_shading(rgb,labels);self.assertTrue(any(r.tone==3 and r.holes for r in regions))
        image=comic_pixels(regions,640,360)
        np.testing.assert_array_equal(image[40,40,:3],(250,238,220))
        self.assertFalse(np.array_equal(image[140,320,:3],(250,238,220)))
        self.assertFalse(any(r.tone==3 for r in extract_shading(rgb,np.zeros((90,160),np.uint8))))

    def test_pattern_is_fixed_in_viewport_and_shadow_is_dotted(self):
        a=ShadeRegion(0,((0,0),(1,0),(1,1),(0,1)))
        b=ShadeRegion(0,((.1,.1),(.9,.1),(.9,.9),(.1,.9)))
        np.testing.assert_array_equal(comic_pixels((a,),640,360)[80:180,100:400],comic_pixels((b,),640,360)[80:180,100:400])
        helicopter=Entity('heli','car',.5,.5,vehicle_type='helicopter')
        self.assertEqual(contact_shadow_boxes((helicopter,)),())
        shadow=comic_pixels(None,640,360,((.2,.6,.8,.8),))
        alpha=shadow[:,:,3];self.assertTrue(alpha.any());self.assertGreater(np.mean(alpha==0),.9)

    def test_motorcycle_class_passes_detector_postprocessing_and_tracking(self):
        # Deterministic raw class-3 output verifies wiring, not video accuracy.
        detector=YoloXDetector.__new__(YoloXDetector);detector.np=np;detector.cv2=cv2
        detector.width=detector.height=32;detector.grid=np.array([[0,0]],np.float32);detector.strides=np.ones((1,1),np.float32);detector.input_name='input'
        output=np.zeros((1,1,85),np.float32);output[0,0,:5]=(16,16,np.log(20),np.log(20),1);output[0,0,5+3]=.95
        class Session:
            def run(self,*args):return [output]
        detector.session=Session()
        detected,*_=detector.detect_rgb(bytes(32*32*3),32,32)
        self.assertEqual([d.label for d in detected],['motorcycle'])
        tracker=TrackManager();first=tracker.update(detected,0);second=tracker.update(detected,.1)
        self.assertEqual(first[0].track_id,second[0].track_id)

    def test_new_presets_clip_at_all_viewport_edges_and_skip_ghosts(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            for material in ('motorcycle','helicopter'):
                for box in ((-.2,.3,.3,.8),(.7,.3,1.2,.8),(.3,-.2,.7,.3),(.3,.8,.7,1.2)):
                    actor=Entity('vehicle','car',.5,.8,bbox=box,vehicle_type=material,yaw=45)
                    scene=Scene(0,0,1,.2,(actor,),frame_clipping=True)
                    canvas.draw(scene);self.assertTrue(canvas.find_withtag('vehicle'))
                    for photo,bounds in canvas._layer_cache.values():
                        if photo:self.assertTrue(0<=bounds[0]<bounds[2]<=640 and 0<=bounds[1]<bounds[3]<=360)
                    canvas.draw(replace(scene,entities=(replace(actor,predicted=True),)))
                    self.assertFalse(canvas.find_withtag('vehicle'))
            actor=Entity('helicopter','car',.5,.85,bbox=(.1,.1,.9,.85),vehicle_type='helicopter',yaw=45)
            scene=Scene(0,0,1,0,(actor,),frame_clipping=True)
            canvas.draw(scene);before=tuple(canvas._layer_cache)
            canvas.draw(replace(scene,animation_time=.1));self.assertNotEqual(before,tuple(canvas._layer_cache))
        finally:root.destroy()

    def test_actor_motion_reuses_background_and_only_rebuilds_cropped_contacts(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            actor=Entity('motorcycle','car',.4,.8,bbox=(.2,.5,.6,.8),vehicle_type='motorcycle',yaw=45)
            scene=Scene(0,0,1,0,(actor,),frame_clipping=True,contact_shadows=True,
                        shading=(ShadeRegion(0,((0,0),(1,0),(1,1),(0,1))),))
            canvas.draw(scene);photo=canvas._background_cache[1];contacts=tuple(canvas._contact_cache)
            canvas.draw(replace(scene,entities=(replace(actor,x=.5,bbox=(.3,.5,.7,.8)),)))
            self.assertIs(canvas._background_cache[1],photo)
            self.assertNotEqual(contacts,tuple(canvas._contact_cache))
            for photo,bounds in canvas._contact_cache.values():
                self.assertLess(photo.width(),640);self.assertLess(photo.height(),30)
                self.assertTrue(0<=bounds[0]<bounds[2]<=640 and 0<=bounds[1]<bounds[3]<=360)
        finally:root.destroy()

if __name__=='__main__':unittest.main()
