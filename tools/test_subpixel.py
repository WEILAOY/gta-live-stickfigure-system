"""Fractional material movement and unchanged rectangular clipping semantics."""
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stickfigure.frame_clipping import FrameLayer


class SubpixelChecks(unittest.TestCase):
    @staticmethod
    def draw(kind, offset, origin=(0, 0)):
        x, y = origin
        layer = FrameLayer((x, y, x + 64, y + 64), (x, y, 64, 64))
        geometry = {
            'line': (20, 12, 20, 48),
            'polygon': (15, 15, 35, 15, 35, 40, 15, 40),
            'oval': (15, 15, 35, 40),
        }[kind]
        coords = [v + (x + offset if i % 2 == 0 else y)
                  for i, v in enumerate(geometry)]
        layer.paint(kind, coords, fill='#34495e', outline='#34495e', width=1)
        return layer

    def test_quarter_pixel_motion_is_visible_for_every_primitive(self):
        # Both positions formerly rounded to the same integer coordinate.
        for kind in ('line', 'polygon', 'oval'):
            with self.subTest(kind=kind):
                a = self.draw(kind, .125).pixels[:, :, 3]
                b = self.draw(kind, .375).pixels[:, :, 3]
                self.assertFalse(np.array_equal(a, b))
                columns = np.arange(a.shape[1], dtype=np.float64)
                ca = (a.sum(axis=0) * columns).sum() / a.sum()
                cb = (b.sum(axis=0) * columns).sum() / b.sum()
                self.assertGreater(cb, ca)
                self.assertLess(cb - ca, .6)

    def test_integer_screen_translation_preserves_local_art(self):
        for kind in ('line', 'polygon', 'oval'):
            with self.subTest(kind=kind):
                a = self.draw(kind, .375)
                b = self.draw(kind, .375, (171, 83))
                self.assertTrue(np.array_equal(a.pixels, b.pixels))

    def test_fractional_viewport_still_clips_only_at_four_edges(self):
        layer = FrameLayer((-200, -200, 300, 300), (10.25, 20.75, 50.5, 40.5))
        layer.paint('polygon', [-200.25, -200.25, 300.25, -200.25,
                                300.25, 300.25, -200.25, 300.25], fill='#34495e')
        self.assertEqual(layer.bounds, (11, 21, 60, 61))
        self.assertEqual(layer.pixels.shape, (40, 49, 4))
        self.assertTrue(layer.pixels[:, :, 3].all())

    def test_light_interior_and_halo_keep_original_compositing(self):
        for halo in (False, True):
            with self.subTest(halo=halo):
                layer = FrameLayer((0, 0, 50, 50), (0, 0, 50, 50), halo=halo)
                layer.paint('polygon', [10.25, 10.25, 40.25, 10.25,
                                        40.25, 40.25, 10.25, 40.25],
                            fill='#f1f5f8', outline='#34495e')
                encoded = layer.png()
                self.assertIsNotNone(encoded)
                decoded = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_UNCHANGED)
                self.assertEqual(decoded[25, 25, 3], 0)
                self.assertGreater(decoded[10, 25, 3], 0)
                self.assertEqual(decoded.shape, (50, 50, 4))

    def test_completely_outside_art_remains_empty(self):
        layer = FrameLayer((200.25, 200.25, 250.75, 250.75), (0, 0, 64, 64))
        layer.paint('oval', [200.25, 200.25, 250.75, 250.75], fill='#34495e')
        self.assertIsNone(layer.png())


if __name__ == '__main__':
    unittest.main()
