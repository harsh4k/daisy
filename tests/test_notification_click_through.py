"""Prove the notification banner's controls are reachable with a real pointer."""
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint
from PyQt6.QtTest import QTest

import main
import settle
import test_hover

WS_EX_TRANSPARENT = 0x20


class ClickThroughProbe:
    """Stand in for the window's extended style so the flag can be observed."""

    def __init__(self, style=WS_EX_TRANSPARENT):
        self.style = style
        self.writes = []

    def get(self, *_args):
        return self.style

    def set(self, _hwnd, _index, value):
        self.writes.append(value)
        self.style = value
        return value


class BannerClickThroughTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def _over_banner(self, window):
        centre = window.notification_banner.mapToGlobal(
            QPoint(window.notification_banner.width() // 2,
                   window.notification_banner.height() // 2))
        return patch.object(main.QCursor, 'pos', return_value=centre)

    def test_banner_stays_clickable_so_its_dismiss_control_works(self):
        window = self.window({'motion_mode': 'reduced'})
        window.show_notification('Codex', 'Needs approval', 'Allow this command?')
        test_hover.APP.processEvents()
        banner = window.notification_banner
        self.assertFalse(banner.isHidden())

        probe = ClickThroughProbe()
        user32 = main.ctypes.windll.user32
        with patch.object(user32, 'GetWindowLongW', probe.get), \
             patch.object(user32, 'SetWindowLongW', probe.set):
            # The pointer moves onto the banner while the overlay is click-through.
            with self._over_banner(window):
                window.check_mouse_position()
            self.assertTrue(probe.writes, 'the click-through flag was never updated')
            self.assertFalse(probe.style & WS_EX_TRANSPARENT,
                             'a notification banner must stay clickable over the pointer')

        # And the dismiss control must work with a real press, not only a slot call.
        QTest.mouseClick(banner.dismiss, __import__('PyQt6.QtCore', fromlist=['Qt'])
                         .Qt.MouseButton.LeftButton)
        self.assertTrue(settle.settle_shell(window))
        self.assertEqual(window.current_state, 'Idle')

    def test_overlay_returns_to_click_through_when_the_pointer_leaves(self):
        window = self.window({'motion_mode': 'reduced'})
        window.show_notification('Codex', 'Needs approval', 'Allow this command?')
        test_hover.APP.processEvents()
        # Daisy is a tool window: it does not hold the keyboard while a toast shows.
        focused = test_hover.APP.focusWidget()
        if focused is not None:
            focused.clearFocus()
        probe = ClickThroughProbe(style=0)
        user32 = main.ctypes.windll.user32
        with patch.object(user32, 'GetWindowLongW', probe.get), \
             patch.object(user32, 'SetWindowLongW', probe.set):
            with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
                window.check_mouse_position()
            self.assertTrue(probe.style & WS_EX_TRANSPARENT,
                            'the overlay must become click-through away from the island')


if __name__ == '__main__':
    unittest.main()
