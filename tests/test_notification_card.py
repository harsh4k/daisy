import unittest
from unittest.mock import patch
from PyQt6.QtCore import QPoint, QRect, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
import main
import settle
import test_hover

APP = test_hover.APP


class NotificationCardTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def card_bounds(self, w):
        return QRect(w.notification_banner.mapTo(w, QPoint()), w.notification_banner.size())

    def test_arrival_swells_the_pill_and_drops_a_porcelain_card(self):
        w = self.window({'motion_mode': 'full'})
        w.show_notification('Claude', 'Run a command in DynamicIsland?', 'npm run build')
        samples = []
        timer = QTimer(w)
        timer.timeout.connect(lambda: samples.append(w.notification_card.progress))
        timer.start(10)
        QTest.qWait(500)
        timer.stop()
        self.assertTrue(any(0. < p < 1. for p in samples), 'the card should be seen dropping in')
        self.assertTrue(settle.settle_shell(w))
        card = w.notification_card
        self.assertEqual((w.island_w, w.island_h), (w.NOTIFY_W, w.NOTIFY_H))
        self.assertEqual(card.progress, 1.)
        self.assertIsNone(card.pixmap, 'live widgets return at rest')
        self.assertFalse(w.notification_banner.isHidden())
        self.assertEqual(w.chip_text.full_text, 'Claude')
        bounds = self.card_bounds(w)
        self.assertGreater(bounds.top(), w.get_island_rect().bottom())
        self.assertTrue(w.rect().contains(bounds))
        self.assertLessEqual(abs(bounds.center().x() - w.get_island_rect().center().x()), 1)

    def test_card_body_is_porcelain(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Discord', 'A title', 'A message')
        APP.processEvents()
        rect = w.notification_card.rest_rect()
        image = w.grab().toImage()
        ratio = image.devicePixelRatio()
        # Just inside the lower-right corner, clear of text and of the rounded edge.
        point = rect.bottomRight() - main.QPointF(24, 6)
        pixel = image.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
        porcelain = QColor(w.theme['porcelain_card'])
        self.assertLessEqual(max(abs(pixel.red() - porcelain.red()), abs(pixel.green() - porcelain.green()),
                                 abs(pixel.blue() - porcelain.blue())), 8, pixel.getRgb())

    def test_status_changes_stay_in_the_pill_without_a_card(self):
        w = self.window({'motion_mode': 'full'})
        w.show_key_event('Caps Lock', True)
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.chip_text.full_text, 'Caps Lock · On')
        self.assertEqual(w.notification_card.progress, 0.)
        self.assertTrue(w.notification_banner.isHidden())

    def test_status_change_replacing_a_card_lifts_the_card_away(self):
        w = self.window({'motion_mode': 'full'})
        w.show_notification('Discord', 'A title', 'A message')
        self.assertTrue(settle.settle_shell(w))
        w.show_key_event('Caps Lock', False)
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.notification_card.progress, 0.)
        self.assertTrue(w.notification_banner.isHidden())

    def test_dismiss_lifts_the_card_and_shrinks_the_overlay(self):
        w = self.window({'motion_mode': 'full'})
        w.show_notification('Discord', 'A title', 'A message')
        self.assertTrue(settle.settle_shell(w))
        tall = w.height()
        w.notification_banner.dismiss.click()
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Idle')
        self.assertEqual(w.notification_card.progress, 0.)
        self.assertLess(w.height(), tall, 'the overlay hugs the pill again')

    def test_resting_pointer_holds_the_notification(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Discord', 'A title', 'A message')
        APP.processEvents()
        self.assertTrue(w.revert_timer.isActive())
        centre = w.notification_banner.mapToGlobal(w.notification_banner.rect().center())
        user32 = main.ctypes.windll.user32
        with patch.object(user32, 'GetWindowLongW', return_value=0x20), \
             patch.object(user32, 'SetWindowLongW', return_value=0):
            with patch.object(main.QCursor, 'pos', return_value=centre):
                w.check_mouse_position()
            self.assertFalse(w.revert_timer.isActive(), 'hovering the card pauses its timeout')
            with patch.object(main.QCursor, 'pos', return_value=QPoint(-5000, -5000)):
                w.check_mouse_position()
            self.assertTrue(w.revert_timer.isActive(), 'leaving the card resumes it')

    def test_reduced_motion_shows_and_removes_the_card_at_once(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Discord', 'A title', 'A message')
        self.assertEqual(w.notification_card.progress, 1.)
        self.assertFalse(w.notification_banner.isHidden())
        w.dismiss_notification()
        self.assertEqual(w.notification_card.progress, 0.)
        self.assertTrue(w.notification_banner.isHidden())


if __name__ == '__main__':
    unittest.main()
