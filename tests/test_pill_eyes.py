import unittest
import settle
import test_hover


class PillEyesTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_eyes_show_in_the_pill_with_or_without_music(self):
        w = self.window({'motion_mode': 'reduced'})
        for state in ('Idle', 'Playing', 'Paused', 'Idle'):
            w.update_media(state, 'Song' if state != 'Idle' else '', 'Artist', '')
            w.update_content()
            self.assertFalse(w.daisy_eyes.isHidden(), state)
        self.assertTrue(w.status_text.isHidden(), 'no timer, no clock text: the eyes are the face')

    def test_eyes_are_centred_between_the_leading_and_trailing_slots(self):
        w = self.window({'motion_mode': 'reduced'})
        w.update_media('Idle', '', '', '')
        w.update_content()
        test_hover.APP.processEvents()
        centre = w.daisy_eyes.mapTo(w.header_widget, w.daisy_eyes.rect().center()).x()
        self.assertAlmostEqual(centre, w.header_widget.width() / 2, delta=3)


if __name__ == '__main__':
    unittest.main()
