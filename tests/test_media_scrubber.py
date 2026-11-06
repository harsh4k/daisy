"""The playback scrubber is a quiet line, not a highlighted brand bar."""
import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtTest import QTest

import test_hover


class ScrubberTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def playing(self, w):
        w.change_state('Hover')
        w.select_feature('dashboard')
        test_hover.APP.processEvents()
        w.dashboard.update_media('Playing', 'Track', 'Artist', '')
        w.dashboard.set_capabilities({'previous': True, 'play_pause': True,
                                      'next': True, 'seek': True})
        w.dashboard.update_timeline(63, 240)
        test_hover.APP.processEvents()
        return w.dashboard.progress

    def test_scrubber_is_neutral_and_not_the_brand_accent(self):
        w = self.window({'motion_mode': 'reduced'})
        scrubber = self.playing(w)
        accent = QColor(w.theme['accent'])
        self.assertNotEqual(scrubber._played_color.name(), accent.name(),
                            'the played part must not be painted in the brand colour')
        self.assertNotEqual(scrubber._track_color.name(), accent.name())
        # The track is quieter than the played part, and both are neutral.
        self.assertLess(scrubber._track_color.alpha(), scrubber._played_color.alpha())
        self.assertEqual(scrubber._track_color.rgb() & 0x00FFFFFF,
                         scrubber._played_color.rgb() & 0x00FFFFFF)

    def test_scrubber_shows_a_handle_only_while_hovered(self):
        w = self.window({'motion_mode': 'reduced'})
        scrubber = self.playing(w)
        scrubber.setValue(500)
        scrubber.resize(300, 32)
        scrubber.show()
        test_hover.APP.processEvents()

        def render():
            image = QImage(scrubber.size(), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            scrubber.render(image)
            return image

        idle = render()
        scrubber._hovered = True
        hovered = render()
        scrubber._hovered = False
        self.assertNotEqual(idle, hovered,
                            'the handle must appear while the pointer is over the scrubber')

    def test_scrubber_keeps_its_keyboard_and_drag_behaviour(self):
        w = self.window({'motion_mode': 'reduced'})
        scrubber = self.playing(w)
        scrubber.setFocus()
        before = scrubber.value()
        QTest.keyClick(scrubber, Qt.Key.Key_Right)
        self.assertGreater(scrubber.value(), before)
        self.assertTrue(scrubber.isEnabled())


if __name__ == '__main__':
    unittest.main()
