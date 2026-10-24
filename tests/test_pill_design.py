import time
import unittest
from PyQt6.QtCore import QPoint, QRect, QRectF
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
import test_hover
import aurora

APP = test_hover.APP


class PillDesignTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def rect_of(self, w, widget):
        return QRect(widget.mapTo(w, QPoint()), widget.size())

    def test_redesign_moves_gif_and_plain_clock_to_aurora_once(self):
        for legacy in ('Custom GIF', 'Clock'):
            w = self.window({'idle_icon': legacy, 'custom_idle_icon': 'C:/old/pill.gif'})
            self.assertEqual(w.settings['idle_icon'], 'Aurora')
            self.assertEqual(w.settings['custom_idle_icon'], 'C:/old/pill.gif', 'the GIF stays selectable')
            self.assertEqual(w.settings['design_version'], 2)
        w = self.window({'idle_icon': 'Clock', 'design_version': 2})
        self.assertEqual(w.settings['idle_icon'], 'Clock', 'a choice made after the redesign is kept')
        w = self.window({'idle_icon': 'Orbit'})
        self.assertEqual(w.settings['idle_icon'], 'Orbit', 'deliberate animated styles are kept')

    def test_orb_drifts_slowly_and_stops_for_reduced_motion(self):
        w = self.window({'motion_mode': 'full'})
        icon = w.status_icon
        self.assertEqual(icon.style_name, 'Aurora')
        self.assertTrue(icon.loop_timer.isActive())
        self.assertEqual(icon.loop_timer.interval(), aurora.ORB_FPS_MS)
        before = icon.pixmap().toImage()
        QTest.qWait(400)
        self.assertNotEqual(before, icon.pixmap().toImage(), 'the light inside the orb drifts')
        w.settings['motion_mode'] = 'reduced'
        w.apply_visual_preferences()
        w.update_content()
        self.assertFalse(icon.loop_timer.isActive())

    def test_audio_bars_appear_only_with_media_and_follow_the_album_colour(self):
        w = self.window({'motion_mode': 'full'})
        bars = w.now_playing
        self.assertFalse(bars.isVisibleTo(w))
        w.update_media('Playing', 'Song', 'Artist', '#1db954')
        APP.processEvents()
        self.assertTrue(bars.isVisibleTo(w))
        self.assertTrue(bars.timer.isActive())
        self.assertEqual(bars.tint, QColor('#1db954'))
        self.assertEqual(w.ambient_tint(), QColor('#1db954'))
        w.update_media('Paused', 'Song', 'Artist', '#1db954')
        self.assertTrue(bars.isVisibleTo(w))
        self.assertFalse(bars.timer.isActive(), 'paused bars hold still')
        w.update_media('Idle', '', '', '#000000')
        self.assertFalse(bars.isVisibleTo(w))
        self.assertEqual(w.ambient_tint(), QColor(w.theme['accent']))

    def test_leading_and_trailing_slots_mirror_around_a_centred_clock(self):
        for style in ('Default', 'Notch Nook'):
            w = self.window({'island_style': style})
            APP.processEvents()
            shell = w.get_island_rect()
            orb = self.rect_of(w, w.status_icon)
            trailing = self.rect_of(w, w.trailing_slot)
            text = self.rect_of(w, w.status_text)
            self.assertEqual(orb.size(), trailing.size())
            self.assertLessEqual(abs((orb.left() - shell.left()) - (shell.right() - trailing.right())), 1.5)
            self.assertLessEqual(abs(text.center().x() - shell.center().x()), 1.5)
            self.assertLessEqual(abs(orb.center().y() - shell.center().y()), 1.5)

    def test_notch_has_small_concave_ears_and_round_lower_corners(self):
        w = self.window({'island_style': 'Notch Nook'})
        rect = QRectF(100, 0, 180, 40)
        outline = w.notch_outline(rect).boundingRect()
        self.assertAlmostEqual(outline.width(), 180 + 2 * w.NOTCH_EAR, places=3)
        self.assertEqual(w.get_current_radius(), 12.)
        w.set_island_size(624, 272)
        self.assertEqual(w.get_current_radius(), 28.)

    def test_bar_levels_stay_in_range_and_keep_moving(self):
        samples = [aurora.bar_levels(t / 30) for t in range(300)]
        self.assertTrue(all(0. <= level <= 1. for frame in samples for level in frame))
        self.assertGreater(len({round(frame[0], 2) for frame in samples}), 30)


if __name__ == '__main__':
    unittest.main()
