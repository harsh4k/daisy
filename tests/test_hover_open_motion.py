"""The edge line, the pill and the open island must read as one continuous motion."""
import unittest
from PyQt6.QtCore import QPoint
from PyQt6.QtTest import QTest
import test_hover
import settle
import ignite_motion as ignite


class HoverOpenMotionTests(unittest.TestCase):
    def window(self):
        helper = test_hover.HoverTests()
        window = helper.window()
        self.addCleanup(helper.doCleanups)
        return window

    def frames(self, w, duration_ms):
        """Sample (width, height, top edge) on every geometry update."""
        samples = []
        original = w.set_island_size

        def logged(width, height):
            original(width, height)
            samples.append((w.island_w, w.island_h, w.get_island_rect().top()))
        w.set_island_size = logged
        self.addCleanup(lambda: setattr(w, 'set_island_size', original) if 'set_island_size' in w.__dict__ else None)
        QTest.qWait(duration_ms)
        return samples

    def to_edge_line(self, w):
        w.change_state('Hidden')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual((w.island_w, w.island_h), (96, 4))
        self.assertEqual(w.get_island_rect().top(), 0)

    def test_island_top_edge_never_snaps_when_opening_is_interrupted(self):
        for hold_ms in (0, 30, 90, 160):
            w = self.window()
            self.to_edge_line(w)
            w.change_state('Idle')
            QTest.qWait(hold_ms)
            w.change_state('Hover')
            samples = self.frames(w, 900)
            self.assertTrue(settle.settle_shell(w))
            ys = [y for _, _, y in samples] + [w.get_island_rect().top()]
            for a, b in zip(ys, ys[1:]):
                self.assertGreaterEqual(b, a - 0.01, ('top edge moved up', hold_ms, ys))
                self.assertLessEqual(b - a, 4.0, ('top edge snapped', hold_ms, ys))
            self.assertEqual(w.get_island_rect().top(), 10)

    def test_interrupted_opening_never_shrinks_or_vanishes(self):
        for hold_ms in (0, 30, 90):
            w = self.window()
            self.to_edge_line(w)
            w.change_state('Idle')
            QTest.qWait(hold_ms)
            start = (w.island_w, w.island_h)
            w.change_state('Hover')
            samples = self.frames(w, 260)
            self.assertTrue(samples)
            self.assertGreaterEqual(min(h for _, h, _ in samples), min(start[1], 4) - 1, ('height collapsed', hold_ms))
            # While the shell is still smaller than the pill it only grows.
            widths = [width for width, _, _ in samples if width < w.IDLE_W - 10]
            for a, b in zip(widths, widths[1:]):
                self.assertGreaterEqual(b, a - 1, ('width dipped', hold_ms, widths))
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual((w.island_w, w.island_h), (624, 284))

    def test_squash_only_applies_to_a_settled_pill(self):
        w = self.window()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        w.change_state('Idle')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual((w.island_w, w.island_h), (w.IDLE_W, w.IDLE_H))
        w.change_state('Hover')
        samples = self.frames(w, ignite.SQUASH_OPEN['squash'] - 10)
        self.assertTrue(samples)
        self.assertLess(min(width for width, _, _ in samples), w.IDLE_W)  # the squash is still there


    def test_motion_snapshot_is_transparent_so_no_grey_panel_flashes(self):
        w = self.window()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        layer = w.content_layer
        layer.capture()
        self.addCleanup(layer.release)
        image = layer.pixmap.toImage()
        # QWidget.grab() filled this with the opaque window colour (grey in dark mode).
        for point in ((2, 2), (image.width() // 2, image.height() - 3), (image.width() - 3, 2)):
            self.assertEqual(image.pixelColor(*point).alpha(), 0, point)
        painted = [image.pixelColor(x, y).alpha() for x in range(0, image.width(), 9) for y in range(0, image.height(), 9)]
        self.assertGreater(max(painted), 200, 'the content itself is still in the picture')


if __name__ == '__main__':
    unittest.main()
