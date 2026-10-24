"""Prove a notification banner never outlives its timeout."""
import unittest

from PyQt6.QtTest import QTest

import test_hover


class NotificationTimeoutTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_banner_returns_to_idle_after_its_timeout(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Codex', 'Needs approval', 'Allow this command?')
        test_hover.APP.processEvents()
        self.assertEqual(w.current_state, 'Notify')
        self.assertTrue(w.revert_timer.isActive())
        QTest.qWait(4200)
        self.assertEqual(w.current_state, 'Idle')

    def test_banner_is_rearmed_after_a_menu_interrupts_its_timeout(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Codex', 'Needs approval', 'Allow this command?')
        test_hover.APP.processEvents()
        self.assertEqual(w.current_state, 'Notify')
        # A menu or dialog stops the timer; the banner must still expire.
        w.revert_timer.stop()
        w.rearm_notification_timer()
        self.assertTrue(w.revert_timer.isActive())
        QTest.qWait(4200)
        self.assertEqual(w.current_state, 'Idle')


if __name__ == '__main__':
    unittest.main()
