import unittest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
import test_hover
import home_card
from home_card import HomeCard, PlayDisc
from theme_tokens import get_theme

APP = test_hover.APP


class HomeCardTests(unittest.TestCase):
    def card(self, title, numeric=False, width=186):
        card = HomeCard('x')
        card.set_theme(get_theme())
        card.resize(width, 176)
        card.set_content('Label', title, 'Detail', 'check', '#1456d9', numeric=numeric)
        self.addCleanup(card.deleteLater)
        return card

    def test_title_shrinks_before_it_is_elided(self):
        font, text = self.card('Done').fit_title(140)
        self.assertEqual((font.pixelSize(), text), (34, 'Done'))
        font, text = self.card('Gym Session').fit_title(140)
        self.assertLess(font.pixelSize(), 34)
        self.assertEqual(text, 'Gym Session')
        font, text = self.card('A very long task name that cannot fit').fit_title(140)
        self.assertEqual(font.pixelSize(), min(home_card.TITLE_SIZES))
        self.assertTrue(text.endswith('…'))

    def test_a_timer_never_changes_size_or_elides(self):
        font, text = self.card('24:56', numeric=True).fit_title(20)
        self.assertEqual(text, '24:56')

    def test_card_is_named_for_screen_readers_and_paints(self):
        card = self.card('Gym Session')
        self.assertEqual(card.accessibleName(), 'Label, Gym Session, Detail')
        self.assertEqual(card.toolTip(), 'Label, Gym Session, Detail')
        self.assertFalse(card.grab().isNull())

    def test_play_disc_toggles_its_glyph_and_clicks(self):
        disc = PlayDisc()
        self.addCleanup(disc.deleteLater)
        clicks = []
        disc.clicked.connect(lambda: clicks.append(1))
        disc.show()
        disc.set_playing(True)
        self.assertTrue(disc.playing)
        QTest.mouseClick(disc, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        self.assertEqual(clicks, [1])
        self.assertEqual(disc.focusPolicy(), Qt.FocusPolicy.TabFocus)

    def test_control_stays_in_the_bottom_right_corner(self):
        card = self.card('Track')
        disc = PlayDisc()
        card.set_control(disc)
        card.resize(200, 180)
        APP.processEvents()
        self.assertGreater(disc.x(), card.width() // 2)
        self.assertGreater(disc.y(), card.height() // 2)
        self.assertLessEqual(disc.x() + disc.width(), card.width())
        self.assertLessEqual(disc.y() + disc.height(), card.height())


if __name__ == '__main__':
    unittest.main()
