from pathlib import Path
import sys,unittest
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.core import ColorRegion
from stickfigure.coloring import extract_colors,color_pixels,ColorStabilizer,PALETTE,FULL


class ColoringChecks(unittest.TestCase):
    def test_equal_luminance_different_hues_remain_distinct(self):
        # Both source colours round to the same gray level (76), yet retain hue.
        image=np.zeros((90,160,3),np.uint8)
        image[:,:80]=(255,0,0);image[:,80:]=(0,130,0)
        gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
        self.assertEqual(int(gray[45,40]),int(gray[45,120]))
        regions=extract_colors(image)
        rendered=color_pixels(regions,160,90)
        self.assertFalse(np.array_equal(rendered[45,25],rendered[45,135]))
        self.assertTrue(all(region.color in PALETTE for region in regions))

    def test_actor_pixels_are_excluded_before_colour_analysis(self):
        first=np.full((90,160,3),(90,145,100),np.uint8)
        second=first.copy()
        first[25:65,60:95]=(230,10,10)
        second[25:65,60:95]=(10,10,230)
        labels=np.zeros((90,160),np.uint8);labels[25:65,60:95]=11
        self.assertEqual(extract_colors(first,labels),extract_colors(second,labels))
        box=((60/160,25/90,95/160,65/90),)
        self.assertEqual(extract_colors(first,exclude_boxes=box),extract_colors(second,exclude_boxes=box))

    def test_fully_excluded_scene_is_empty_and_clears_history(self):
        state=ColorStabilizer();image=np.full((90,160,3),(160,200,220),np.uint8)
        extract_colors(image,stabilizer=state,timestamp=.1,generation=1)
        self.assertIsNotNone(state.previous)
        result=extract_colors(image,np.full((90,160),13,np.uint8),stabilizer=state,timestamp=.2,generation=1)
        self.assertEqual(result,());self.assertIsNone(state.previous)

    def test_geometry_is_bounded_immutable_and_deterministic(self):
        random=np.random.default_rng(31)
        image=random.integers(0,256,(360,640,3),dtype=np.uint8)
        for detail in ('粗略','标准','精细'):
            regions=extract_colors(image,detail=detail)
            self.assertLessEqual(len(regions),129)
            self.assertEqual(regions,extract_colors(image,detail=detail))
            hash(regions)
            self.assertTrue(all(0<=value<=1 for r in regions for p in (r.points,*r.holes) for xy in p for value in xy))

    def test_holes_reveal_underlying_colour_and_viewport_clips(self):
        holes=(((.4,.4),(.6,.4),(.6,.6),(.4,.6)),)
        regions=(ColorRegion('#112233',FULL),
                 ColorRegion('#ccddee',((-.2,.2),(1.2,.2),(1.2,.8),(-.2,.8)),holes))
        image=color_pixels(regions,100,80)
        self.assertEqual(image.shape,(80,100,4))
        self.assertEqual(tuple(image[40,50]),(51,34,17,255))
        self.assertEqual(tuple(image[25,5]),(238,221,204,255))
        self.assertTrue((image[:,:,3]==255).all())

    def test_generation_time_jump_and_abrupt_colour_change_use_current_frame(self):
        state=ColorStabilizer()
        red=np.full((68,120,3),(180,35,35),np.uint8)
        blue=np.full_like(red,(35,35,180))
        state.quantize(red,.1,1)
        got=state.quantize(blue,.2,1)
        expected=ColorStabilizer().quantize(blue,.2,1)
        self.assertTrue(np.array_equal(got,expected));self.assertTrue(state.last_reset)
        state.quantize(red,.3,2);self.assertTrue(state.last_reset)
        state.quantize(blue,.1,2);self.assertTrue(state.last_reset)
        state.quantize(red,2.,2);self.assertTrue(state.last_reset)

    def test_large_camera_translation_does_not_blend_old_colour_edges(self):
        state=ColorStabilizer()
        image=np.full((68,120,3),(170,150,115),np.uint8)
        image[10:50,15:45]=(40,120,65)
        image[25:60,75:105]=(60,90,170)
        state.quantize(image,.1,1)
        moved=np.roll(image,8,axis=1)
        got=state.quantize(moved,.2,1)
        expected=ColorStabilizer().quantize(moved,.2,1)
        self.assertTrue(state.last_reset)
        self.assertTrue(np.array_equal(got,expected))

    def test_empty_regions_are_opaque_paper_without_pattern(self):
        image=color_pixels((),320,180)
        self.assertEqual(len(np.unique(image.reshape(-1,4),axis=0)),1)
        self.assertEqual(tuple(image[0,0]),(252,249,247,255))


if __name__=='__main__':unittest.main()
