from pathlib import Path
import sys,unittest,tkinter as tk
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stickfigure.sprite_cache import SpriteCache
from stickfigure.core import Scene,Entity,TextRegion
from stickfigure.rendering import SceneCanvas
from stickfigure.assets import vehicle_drawing


class SpriteCacheChecks(unittest.TestCase):
    def test_memory_and_item_limits_evict_least_recently_used(self):
        cache=SpriteCache(max_bytes=10,max_items=2)
        cache.put('a',1,4);cache.put('b',2,4)
        self.assertEqual(cache.get('a'),1)
        cache.put('c',3,4)
        self.assertIsNone(cache.get('b'))
        self.assertLessEqual(cache.bytes,10)
        cache.put('large',4,11)
        self.assertIsNone(cache.get('large'))
        cache.clear();self.assertEqual(cache.bytes,0)

    def setUp(self):
        self.root=tk.Tk();self.canvas=SceneCanvas(self.root,width=640,height=360)
        self.canvas.pack();self.root.update()
    def tearDown(self):self.root.destroy()
    def scene(self,actor,epoch=1,t=0):
        return Scene(0,0,epoch,t,(actor,),False,frame_clipping=True)
    def actor(self,**kwargs):
        return replace(Entity('p','person',.5,.8,bbox=(.45,.3,.55,.8)),**kwargs)
    def image(self):return self.canvas._images[0]

    def test_translation_reuses_art_and_moves_hitbox_and_pose(self):
        a=self.actor();self.canvas.draw(self.scene(a));photo=self.image()
        before=self.canvas.hitboxes[0];pose=self.canvas._poses['p'][0]
        b=replace(a,x=a.x+.025,bbox=tuple(v+.025 if i%2==0 else v for i,v in enumerate(a.bbox)))
        self.canvas.draw(self.scene(b))
        self.assertIs(self.image(),photo)
        self.assertEqual(self.canvas.hitboxes[0][0]-before[0],16)
        self.assertAlmostEqual(self.canvas._poses['p'][0][0][0]-pose[0][0],32)

    def test_primary_label_and_action_caption_survive_cache_hit(self):
        a=self.actor(primary=True,action_caption='测试动作')
        self.canvas.draw(self.scene(a));photo=self.image();self.canvas.draw(self.scene(a))
        self.assertIs(self.image(),photo)
        values=[self.canvas.itemcget(i,'text') for i in self.canvas.find_all() if self.canvas.type(i)=='text']
        self.assertIn('主角',values);self.assertIn('测试动作',values)

    def test_fractional_phase_style_and_animation_are_not_stale(self):
        a=self.actor();self.canvas.draw(self.scene(a));photo=self.image()
        offset=.25/640
        b=replace(a,bbox=tuple(v+offset if i%2==0 else v for i,v in enumerate(a.bbox)))
        self.canvas.draw(self.scene(b));self.assertIsNot(self.image(),photo)
        self.canvas.draw(self.scene(replace(a,primary=True)));self.assertIsNot(self.image(),photo)
        a=replace(a,action='WALK');self.canvas.draw(self.scene(a,t=.1));photo=self.image()
        self.canvas.draw(self.scene(a,t=.3));self.assertIsNot(self.image(),photo)

    def test_cached_material_does_not_restore_missing_actor_or_cross_epoch(self):
        a=self.actor();self.canvas.draw(self.scene(a));photo=self.image()
        self.canvas.draw(replace(self.scene(a),entities=()))
        self.assertFalse(self.canvas.find_withtag('preset-object'))
        self.canvas.draw(self.scene(replace(a,predicted=True)))
        self.assertFalse(self.canvas.find_withtag('preset-object'))
        self.canvas.draw(self.scene(a,epoch=2));self.assertIsNot(self.image(),photo)

    def test_moving_to_edge_rasterizes_new_viewport_crop(self):
        a=Entity('car','car',.5,.8,bbox=(.3,.5,.7,.8),yaw=90)
        self.canvas.draw(self.scene(a));photo=self.image()
        edge=replace(a,x=.03,bbox=(0,.5,.15,.8),render_bbox=(-.25,.5,.15,.8))
        self.canvas.draw(self.scene(edge));self.assertIsNot(self.image(),photo)
        for _,bounds in self.canvas._layer_cache.values():
            self.assertTrue(0<=bounds[0]<=bounds[2]<=640)

    def test_vehicle_aspect_and_material_share_one_mesh(self):
        a=Entity('car','car',.5,.8,bbox=(.3,.4,.7,.8),yaw=45)
        with patch('stickfigure.rendering.vehicle_drawing',wraps=vehicle_drawing) as material:
            self.canvas.draw(self.scene(a))
            self.assertEqual(material.call_count,1)


if __name__=='__main__':unittest.main()
