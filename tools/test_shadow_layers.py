from pathlib import Path
import sys,unittest
from dataclasses import replace
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.core import ShadeRegion
from stickfigure.shading import extract_shading,comic_pixels,contact_layer,ShadingStabilizer,TONE_ORDER,DETAILS

FULL=((0,0),(1,0),(1,1),(0,1))
class ShadowLayerChecks(unittest.TestCase):
    def test_six_brightness_bands_and_optional_three_four_levels(self):
        for value,tone in ((20,6),(70,5),(110,0),(150,1),(195,4),(240,2)):
            rgb=np.full((90,160,3),value,np.uint8)
            self.assertEqual({r.tone for r in extract_shading(rgb)},{tone})
        gradient=np.repeat(np.linspace(0,255,360,dtype=np.uint8)[None,:,None],180,axis=0).repeat(3,axis=2)
        for levels in (3,4,6):
            regions=extract_shading(gradient,levels=levels)
            self.assertEqual(len({r.tone for r in regions}),levels)
    def test_all_tones_are_distinct_and_keep_paper(self):
        darkness=[]
        for tone in reversed(TONE_ORDER):
            image=comic_pixels((ShadeRegion(tone,FULL),),640,360)
            self.assertGreater(np.mean(np.all(image[:,:,:3]==255,axis=2)),.4)
            self.assertGreaterEqual(image[:,:,:3].min(),100)
            darkness.append(255-image[:,:,:3].mean())
        self.assertTrue(all(b>a for a,b in zip(darkness,darkness[1:])),darkness)
    def test_density_changes_marks_without_moving_region(self):
        r=(ShadeRegion(6,((.2,.2),(.8,.2),(.8,.8),(.2,.8))),)
        counts=[]
        for density in ('疏','中等','密'):
            p=comic_pixels(r,640,360,density=density)
            self.assertTrue(np.all(p[:50,:,:3]==255))
            counts.append(np.count_nonzero(np.any(p[:,:,:3]<255,axis=2)))
        self.assertLess(counts[0],counts[1]);self.assertLess(counts[1],counts[2])
    def test_small_threshold_noise_holds_and_real_change_is_immediate(self):
        stable=ShadingStabilizer();observed=[]
        for i,v in enumerate((128,132,128,132,129,131)):
            observed.append(int(stable.quantize(np.full((68,120),v,np.uint8),6,i*.2,1)[0,0]))
        self.assertEqual(len(set(observed)),1,observed)
        current=stable.quantize(np.full((68,120),230,np.uint8),6,1.2,1)
        self.assertTrue(stable.last_reset);self.assertTrue(np.all(current==2))
    def test_generation_seek_gap_and_explicit_reset_discard_history(self):
        stable=ShadingStabilizer()
        for timestamp,generation in ((0,1),(.2,2),(.1,2),(2,2)):
            stable.quantize(np.full((68,120),128,np.uint8),6,timestamp,generation)
            self.assertTrue(stable.last_reset)
        stable.reset();self.assertIsNone(stable.previous)
    def test_moving_edges_adopt_new_position_without_trails(self):
        stable=ShadingStabilizer();a=np.full((68,120),220,np.uint8);a[:,20:45]=20
        stable.quantize(a,6,0,1);b=np.full_like(a,220);b[:,60:85]=20
        out=stable.quantize(b,6,.2,1)
        self.assertTrue(np.all(out[:,20:45]==2));self.assertTrue(np.all(out[:,60:85]==6))
    def test_finer_partition_preserves_a_small_shadow_and_excludes_actors(self):
        image=np.full((180,320,3),240,np.uint8);image[75:95,145:165]=30
        regions=extract_shading(image,detail='精细');self.assertTrue(any(r.tone==6 for r in regions))
        boxed=extract_shading(image,exclude_boxes=((.42,.35,.57,.6),),detail='精细')
        self.assertEqual({r.tone for r in boxed},{2})
        for detail in DETAILS:
            self.assertLessEqual(len(extract_shading(image,detail=detail)),145)
    def test_contact_shadow_has_two_dotted_zones_and_clips(self):
        p,bounds=contact_layer((.2,.5,.8,.8),640,360)
        colors=np.unique(p[p[:,:,3]>0,:3],axis=0)
        self.assertEqual(len(colors),2);self.assertGreater(np.mean(p[:,:,3]==0),.65)
        for box in ((-.2,.6,.2,.8),(.8,.6,1.2,.8),(.2,-.1,.8,.1),(.2,.9,.8,1.1)):
            p,(l,t,r,b)=contact_layer(box,640,360)
            self.assertTrue(0<=l<r<=640 and 0<=t<b<=360)
            self.assertEqual(p.shape[:2],(b-t,r-l))

if __name__=='__main__':unittest.main()
