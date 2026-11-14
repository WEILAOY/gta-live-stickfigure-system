from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.assets import flash_stage,weapon_muzzle,weapon_recoil,muzzle_flash_faces,combat_drawing,person_props,FLASH_DURATION
from stickfigure.core import Scene,Entity
from stickfigure.rendering import SceneCanvas

class MuzzleChecks(unittest.TestCase):
    def test_two_three_state_materials_and_time_boundaries(self):
        for t,stage in ((-.01,None),(0,0),(.019,0),(.020,1),(.089,1),(.090,2),(.119,2),(.120,None),(.449,None),(.46,0)):
            self.assertEqual(flash_stage(t),stage)
        self.assertNotEqual(muzzle_flash_faces('pistol',1),muzzle_flash_faces('rifle',1))
        for weapon in ('pistol','rifle'):
            faces=[muzzle_flash_faces(weapon,i) for i in range(3)]
            self.assertEqual(len(set(faces)),3)
            self.assertTrue(all(len(f)==6 and any(p.fill=='#ffffff' for p in f) for f in faces))
            peak=max(p[2] for f in faces[1] for p in f.points)
            self.assertGreater(peak,max(p[2] for f in faces[0] for p in f.points))
            self.assertFalse(muzzle_flash_faces(weapon,None))

    def test_flash_base_and_barrel_share_exact_recoil_anchor(self):
        for weapon,z in (('pistol',.50),('rifle',.79)):
            for t in (0,.05,.105,.2):
                muzzle=weapon_muzzle(weapon,'GUN_FIRE',t)
                self.assertAlmostEqual(muzzle[2],z-weapon_recoil('GUN_FIRE',t))
                self.assertEqual(weapon_muzzle(weapon,'GUN_HOLD',t)[2],z)
                for f in muzzle_flash_faces(weapon,flash_stage(t))[:2]:
                    self.assertIn((0,0,0),f.points)

    def test_all_views_and_mirrors_stay_in_constant_bounds_and_stop_clears_flash(self):
        for weapon in ('pistol','rifle'):
            for yaw in range(0,360,15):
                for mirror in (False,True):
                    for t in (.01,.05,.105,.121):
                        drawing=combat_drawing('GUN_FIRE',t,weapon,yaw,mirror=mirror)
                        self.assertTrue(all(0<=v<=1 for p in drawing.shapes for v in p.points),(weapon,yaw,t))
                        self.assertEqual(any(p.role=='muzzle-flash' for p in drawing.shapes),t<FLASH_DURATION)
            self.assertFalse(any(p.role=='muzzle-flash' for p in combat_drawing('GUN_HOLD',.05,weapon).shapes))
            for t in (.01,.05,.105):
                self.assertTrue(all(0<=v<=1 for p in person_props('GUN_FIRE',t,weapon=weapon) for v in p.points))

    def test_15_and_30fps_sample_same_time_envelope_and_visible_peak(self):
        for fps in (15,30):
            for offset in np.linspace(0,1/fps,17,endpoint=False):
                times=np.arange(offset,.3,1/fps)
                active=[t for t in times if flash_stage(t) is not None]
                self.assertTrue(active);self.assertTrue(any(flash_stage(t)==1 for t in active))
                self.assertLess(active[-1],FLASH_DURATION)
                self.assertLessEqual(active[-1]+1/fps,FLASH_DURATION+1/fps+1e-8)

    def test_actual_color_pixels_clear_and_clip_without_whole_canvas_whiteout(self):
        root=tk.Tk();c=SceneCanvas(root,width=640,height=360);c.pack();root.update()
        def pixels(photo):
            raw=photo.tk.call(str(photo),'data','-format','png')
            return cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_UNCHANGED)
        try:
            actor=Entity('shooter','person',.4,.85,bbox=(.34,.20,.46,.85),action='GUN_FIRE',action_time=.05,weapon='rifle',combat_yaw=90)
            scene=Scene(0,0,1,0,(actor,),frame_clipping=True)
            c.draw(scene);before=pixels(c._images[0]);self.assertTrue(np.any((before[:,:,2]>180)&(before[:,:,0]<160)))
            c.draw(replace(scene,entities=(replace(actor,action='GUN_HOLD'),)))
            after=pixels(c._images[0]);self.assertFalse(np.any((after[:,:,2]>180)&(after[:,:,0]<160)))
            for box in ((-.15,.2,.05,.8),(.90,.2,1.1,.8),(.3,-.1,.45,.45),(.3,.7,.45,1.15)):
                c.draw(replace(scene,entities=(replace(actor,bbox=box),)))
                for photo,bounds in c._layer_cache.values():
                    if photo:self.assertTrue(0<=bounds[0]<bounds[2]<=640 and 0<=bounds[1]<bounds[3]<=360)
                self.assertFalse(c.find_withtag('shade-background'))
        finally:root.destroy()

if __name__=='__main__':unittest.main()
