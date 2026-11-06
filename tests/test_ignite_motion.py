import unittest
from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtTest import QTest
import test_hover
import settle
import ignite_motion as ignite

APP = test_hover.APP


class SpringMathTests(unittest.TestCase):
    def timeline(self, start, end, profile, step=5):
        return [ignite.shell_size(start, end, ms, profile)
                for ms in range(0, ignite.total_ms(profile) + step, step)]

    def test_spring_starts_at_rest_overshoots_once_and_settles(self):
        k, c = ignite.OPEN['w']
        self.assertEqual(ignite.spring(0, k, c), 0.)
        peak = max(ignite.spring(ms / 1000, k, c) for ms in range(1, 600))
        self.assertTrue(1.05 < peak < 1.15, peak)
        self.assertAlmostEqual(ignite.spring(ignite.OPEN['settle'] / 1000, k, c), 1., places=2)

    def test_opening_from_the_pill_squashes_overshoots_and_lands_exactly(self):
        frames = self.timeline((180, 40), (624, 272), ignite.SQUASH_OPEN)
        self.assertEqual(frames[0], (180, 40))
        squashed = ignite.shell_size((180, 40), (624, 272), ignite.SQUASH_OPEN['squash'] - 1, ignite.SQUASH_OPEN)
        self.assertLess(squashed[0], 180)
        self.assertLess(squashed[1], 40)
        self.assertGreater(max(w for w, _ in frames), 624)
        self.assertGreater(max(h for _, h in frames), 272)
        self.assertEqual(frames[-1], (624, 272))

    def test_height_lags_width_so_the_shape_stretches_first(self):
        w, h = ignite.shell_size((180, 40), (480, 112), 30, ignite.OPEN)
        self.assertGreater(w, 180)
        self.assertEqual(h, 40)

    def test_closing_dips_below_the_pill_then_settles(self):
        frames = self.timeline((624, 272), (180, 40), ignite.CLOSE)
        self.assertLess(min(w for w, _ in frames), 180)
        self.assertEqual(frames[-1], (180, 40))

    def test_rim_light_fades_in_holds_and_turns_once(self):
        self.assertEqual(ignite.rim_alpha(0.), 0.)
        self.assertEqual(ignite.rim_alpha(1.), 0.)
        self.assertEqual(ignite.rim_alpha(.5), 1.)
        self.assertEqual(ignite.rim_angle(0.), 120.)
        self.assertEqual(ignite.rim_angle(1.), -240.)


class IgniteWindowTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def clear_focus(self):
        if APP.focusWidget():
            APP.focusWidget().clearFocus()

    def sample(self, w, duration):
        samples = []
        timer = QTimer(w)
        timer.setInterval(10)
        layer = w.content_layer
        timer.timeout.connect(lambda: samples.append((w.island_w, w.island_h, w.ignite_phase,
                                                      layer.active and layer.pixmap is not None and layer.sharpness < 1.)))
        timer.start()
        QTest.qWait(duration)
        timer.stop()
        return samples

    def assert_settled(self, w, size):
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual((w.island_w, w.island_h), size)
        self.assertEqual(w.content_opacity.opacity(), 1.)
        self.assertFalse(w.content_layer.active, 'live widgets return at rest')
        self.assertFalse(w.island_root.isHidden())
        self.assertIsNone(w.content_layer.pixmap)
        self.assertEqual(w.content_layer.rise, 0)
        self.assertEqual(w.content_container.pos(), QPoint(0, 0))
        self.assertEqual(w.ignite_phase, 0.)
        self.assertIsNone(w.content_container.graphicsEffect(), 'no live graphics effect at rest')

    def test_opening_springs_past_its_size_and_sharpens_content_without_rim(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hover')
        samples = self.sample(w, 700)
        self.assertGreater(max(s[0] for s in samples), 624, 'the shell should overshoot, then settle')
        self.assertFalse(any(0. < s[2] < 1. for s in samples), 'opening it yourself stays quiet: no rim light')
        self.assertTrue(any(s[3] for s in samples), 'content should arrive as a soft snapshot, then sharpen')
        self.assert_settled(w, (624, 272))

    def test_notification_arrival_uses_ignite_and_settles(self):
        w = self.window({'motion_mode': 'full'})
        w.show_notification('Claude', 'Run a command?', 'npm run build')
        samples = self.sample(w, 400)
        self.assertTrue(any(0. < s[2] < 1. for s in samples))
        self.assert_settled(w, (w.NOTIFY_W, w.NOTIFY_H))

    def test_rapid_reversal_clears_every_effect(self):
        w = self.window({'motion_mode': 'full'})
        for state in ('Hover', 'Idle', 'Hover', 'Idle'):
            self.clear_focus()
            w.change_state(state)
            QTest.qWait(120)
        self.assert_settled(w, (180, 40))

    def test_rim_light_is_visible_while_it_runs(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hover')
        self.assert_settled(w, (624, 272))
        before = w.grab().toImage()
        ignite.set_rim(w, .4)
        self.assertNotEqual(before, w.grab().toImage())
        ignite.set_rim(w, 0.)
        self.assertEqual(before, w.grab().toImage())

    def test_reduced_motion_has_no_spring_light_or_blur(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        self.assertEqual((w.island_w, w.island_h), (624, 272))
        self.assertEqual(w.ignite_phase, 0.)
        self.assertFalse(w.content_layer.active)
        self.assertEqual(w.content_layer.rise, 0)

    def test_focused_controls_are_never_hidden_by_a_snapshot(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hover')
        self.assert_settled(w, (624, 272))
        w.nav_buttons[1].setFocus()
        APP.processEvents()
        w.select_feature('tools')
        self.assertFalse(w.island_root.isHidden(), 'keyboard focus keeps the live content')
        self.assertTrue(settle.settle_shell(w))
        self.assertTrue(w.tools_panel.isVisible())

    def test_snapshot_paints_inside_the_island_while_moving(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hover')
        QTest.qWait(320)
        layer = w.content_layer
        self.assertTrue(layer.active)
        self.assertTrue(w.island_root.isHidden(), 'live widgets rest while the shell moves')
        self.assertIsNotNone(layer.pixmap)
        self.assert_settled(w, (624, 272))


if __name__ == '__main__':
    unittest.main()
