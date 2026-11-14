"""Size-dependent decoration must not alter material scale or structural paths."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import math
import unittest
from stickfigure.assets import detail_for_size, vehicle_drawing, dog_drawing


class MaterialDetailChecks(unittest.TestCase):
    def test_size_hysteresis_avoids_switching_on_small_box_fluctuations(self):
        self.assertEqual(detail_for_size(79),'compact')
        self.assertEqual(detail_for_size(80),'standard')
        current='compact'
        for height in (79,82,77,85,87):
            current=detail_for_size(height,current)
            self.assertEqual(current,'compact')
        current=detail_for_size(88,current)
        self.assertEqual(current,'standard')
        for height in (87,82,79,75,72):
            current=detail_for_size(height,current)
            self.assertEqual(current,'standard')
        self.assertEqual(detail_for_size(71,current),'compact')

    def test_compact_preserves_every_structural_path_and_scale_across_views(self):
        for kind in ('car','truck','boat','motorcycle','helicopter'):
            for yaw in range(0,360,45):
                for pitch in (0,22,78):
                    with self.subTest(kind=kind,yaw=yaw,pitch=pitch):
                        full=vehicle_drawing(yaw,pitch,kind,22.5)
                        small=vehicle_drawing(yaw,pitch,kind,22.5,detail='compact')
                        self.assertEqual(full.aspect,small.aspect)
                        self.assertLess(len(small.shapes),len(full.shapes))
                        self.assertEqual(small.shapes,tuple(s for s in full.shapes if s.role!='detail'))
                        self.assertTrue(all(math.isfinite(v) and -.00001<=v<=1.00001
                                            for shape in small.shapes for v in shape.points))
                        self.assertTrue(any(s.role=='body' for s in small.shapes))
                        if kind in ('car','truck','motorcycle'):
                            self.assertTrue(any(s.role=='wheel' for s in small.shapes))

    def test_default_calls_and_cached_detail_variants_are_compatible(self):
        self.assertEqual(vehicle_drawing(45,22),vehicle_drawing(45,22,detail='standard'))
        self.assertIs(vehicle_drawing(45,22,detail='compact'),vehicle_drawing(45,22,detail='compact'))
        with self.assertRaises(ValueError):vehicle_drawing(detail='invalid')

    def test_window_and_internal_weights_do_not_overpower_car_body(self):
        shapes=vehicle_drawing(45).shapes
        self.assertTrue(any(s.width>=2 for s in shapes if s.role=='body'))
        self.assertTrue(all(s.width<=1.4 for s in shapes if s.role=='window'))
        self.assertTrue(all(s.width<=1.25 for s in shapes if s.role=='detail'))

    def test_dog_keeps_body_legs_ear_and_nose_in_both_directions(self):
        for mirror in (False,True):
            full=dog_drawing(mirror)
            compact=dog_drawing(mirror,'compact')
            self.assertEqual(compact,tuple(s for s in full if s.role!='detail'))
            self.assertEqual(len(compact),9)
            self.assertEqual(len([s for s in compact if s.kind=='oval']),1)  # nose retained
            self.assertEqual(len([s for s in compact if s.kind=='line']),5)  # tail and four legs
        for normal,mirrored in zip(dog_drawing(False),dog_drawing(True)):
            self.assertEqual(normal.kind,mirrored.kind)
            for i,(a,b) in enumerate(zip(normal.points,mirrored.points)):
                self.assertAlmostEqual(a,1-b if i%2==0 else b)


if __name__=='__main__':unittest.main()
