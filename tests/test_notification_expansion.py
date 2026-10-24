"""Notifications must dismiss even when the dashboard had keyboard focus."""
import unittest
from PyQt6.QtCore import QPoint, QRect
import settle
import test_hover


class NotificationExpansionTests(unittest.TestCase):
    def window(self, style='Default'):
        fixture = test_hover.HoverTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.window({'island_style': style})

    def test_hidden_dashboard_focus_does_not_trap_notification(self):
        w = self.window()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        w.activateWindow()
        w.nav_buttons[1].setFocus()
        test_hover.APP.processEvents()
        self.assertTrue(w.has_keyboard_focus())
        w.show_notification('Messages', 'New message', 'A notification preview')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Notify')
        self.assertFalse(w.nav_buttons[1].isVisible())
        w.revert_timer.stop()
        w.revert_timer.timeout.emit()
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Idle')

    def test_replaced_notifications_fit_and_return_to_centered_clock(self):
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w = self.window(style)
            w.show_notification('Messages', 'A long title ' * 8, 'A long body ' * 15)
            w.show_notification('Calendar', 'Reminder', 'Starts now')
            self.assertTrue(settle.settle_shell(w))
            banner = w.notification_banner
            # The replaced notification shows only the newest content.
            self.assertEqual(banner.app.full_text, 'Calendar')
            self.assertEqual(banner.title.full_text, 'Reminder')
            self.assertEqual(banner.message.full_text, 'Starts now')
            bounds = QRect(banner.mapTo(w, QPoint()), banner.size())
            # The newest notification rests in the porcelain card hanging below the island.
            self.assertTrue(w.notification_card.rest_rect().toAlignedRect().contains(bounds))
            self.assertGreater(bounds.top(), w.get_island_rect().bottom())
            self.assertTrue(w.rect().contains(bounds), 'the overlay makes room for the card')
            w.revert_timer.stop()
            w.revert_timer.timeout.emit()
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(w.current_state, 'Idle')
            icon = QRect(w.status_icon.mapTo(w, QPoint()), w.status_icon.size())
            text = QRect(w.status_text.mapTo(w, QPoint()), w.status_text.size())
            self.assertLessEqual(abs(icon.united(text).united(QRect(w.trailing_slot.mapTo(w, QPoint()), w.trailing_slot.size())).center().x() - w.get_island_rect().center().x()), 1)
            self.assertEqual(w.status_text.toolTip(), '')


if __name__ == '__main__':
    unittest.main()
