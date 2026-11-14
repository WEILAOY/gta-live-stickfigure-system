from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.shading import extract_shading,contact_shadow_boxes
from stickfigure.assets import combat_drawing,COMBAT_VIEWS
from stickfigure.combat import combat_scene
from stickfigure.rendering import SceneCanvas
from stickfigure.core import ShadeRegion,TextRegion

class ShadingChecks(unittest.TestCase):
    def test_uniform_tones_and_three_bands(self):
        for value,tone in ((0,0),(120,1),(255,None)):
            regions=extract_shading(np.full((90,160,3),value,np.uint8),levels=3)
            self.assertEqual({r.tone for r in regions},{2} if tone is None else {tone})
        image=np.zeros((90,160,3),np.uint8);image[:,53:106]=120;image[:,106:]=255
        regions=extract_shading(image,levels=3)
        self.assertEqual({r.tone for r in regions},{0,1,2})
        self.assertTrue(all(0<=v<=1 for r in regions for p in r.points for v in p))

    def test_actor_pixels_excluded_semantically_and_by_box(self):
        a=np.full((90,160,3),220,np.uint8);b=a.copy();b[25:65,65:95]=0
        labels=np.zeros((90,160),np.uint8);labels[25:65,65:95]=11
        self.assertEqual(extract_shading(a,labels),extract_shading(b,labels))
        boxes=((.39,.25,.61,.75),)
        self.assertEqual(extract_shading(a,exclude_boxes=boxes),extract_shading(b,exclude_boxes=boxes))
        self.assertEqual(extract_shading(b,np.full((90,160),13,np.uint8)),())

    def test_shadows_are_preset_geometry_and_skip_predictions(self):
        scene=combat_scene(0)
        self.assertEqual(len(contact_shadow_boxes(scene.entities)),2)
        self.assertEqual(contact_shadow_boxes((replace(scene.entities[0],predicted=True),)),())
        self.assertTrue(all(0<=v<=1 for box in contact_shadow_boxes(combat_scene(2).entities) for v in box))

    def test_combat_views_are_distinct_bounded_and_have_simple_line_weapons(self):
        drawings=[]
        for weapon in ('pistol','rifle'):
            for yaw in COMBAT_VIEWS.values():
                for mirror in (False,True):
                    for t in (0,.05,.15):
                        drawing=combat_drawing('GUN_FIRE',t,weapon,yaw,mirror=mirror)
                        self.assertTrue(all(0<=v<=1 for p in drawing.shapes for v in p.points),(weapon,yaw,mirror,t))
                        self.assertTrue(any(p.kind=='line' and p.role=='weapon' for p in drawing.shapes))
                        self.assertFalse(any(p.kind=='polygon' and p.role!='muzzle-flash' for p in drawing.shapes))
                drawings.append(combat_drawing(weapon=weapon,yaw=yaw))
        self.assertEqual(len(set(drawings)),8)
        self.assertGreater(len(combat_drawing(weapon='rifle').shapes),len(combat_drawing(weapon='pistol').shapes))

    def test_actual_renderer_shading_toggle_ocr_and_cache(self):
        root=tk.Tk();canvas=SceneCanvas(root,width=640,height=360);canvas.pack();root.update()
        try:
            base=combat_scene(.82,weapon='rifle')
            scene=replace(base,shading=(ShadeRegion(0,((0,0),(1,0),(1,1),(0,1))),),texts=(TextRegion('测试',1,(.7,.1,.9,.2)),))
            canvas.draw(scene);self.assertTrue(canvas.find_withtag('shade-region'))
            self.assertTrue(canvas.find_withtag('contact-shadow'))
            self.assertEqual(len(contact_shadow_boxes(scene.entities)),2)
            self.assertEqual(canvas.itemcget(canvas.find_withtag('ocr-text')[0],'text'),'测试')
            before=tuple(canvas._layer_cache)
            canvas.draw(base);self.assertFalse(canvas.find_withtag('shade-region'))
            self.assertNotEqual(before,tuple(canvas._layer_cache))
            for yaw in COMBAT_VIEWS.values():
                for x in (.02,.98):
                    actor=replace(base.entities[0],combat_yaw=yaw,bbox=(x-.064,.25,x+.064,.85))
                    canvas.draw(replace(scene,entities=(actor,)))
                    self.assertTrue(canvas._images)
                    for photo,bounds in canvas._layer_cache.values():
                        if photo:self.assertTrue(0<=bounds[0]<bounds[2]<=640 and 0<=bounds[1]<bounds[3]<=360)
        finally:root.destroy()

if __name__=='__main__':unittest.main()
