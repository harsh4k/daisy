"""Browser tab access must not accidentally expand or focus Daisy."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_hover
import main
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest


class BrowserTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def browser_window(self, style='Default'):
        w = self.window({'island_style': style})
        w.browser_guard = SimpleNamespace(is_active=lambda: True, restore_focus=lambda: None)
        w.game_guard = SimpleNamespace(is_active=lambda: False)
        return w

    def test_browser_hover_never_expands(self):
        w = self.browser_window()
        for point in (QPoint(w.width() // 2, 25), QPoint(w.width() // 2, 1)):
            with patch.object(main.QCursor, 'pos', return_value=w.mapToGlobal(point)):
                w.check_mouse_position()
            QTest.qWait(280)
            self.assertEqual(w.current_state, 'Hidden')
        self.assertEqual((w.island_w, w.island_h), (96, 4))

    def test_actual_line_click_opens_then_escape_and_leaving_close_every_shape(self):
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w = self.browser_window(style)
            w.check_mouse_position()
            QTest.qWait(280)
            QTest.mouseClick(w.island_root, Qt.MouseButton.LeftButton,
                             pos=QPoint(w.island_root.width() // 2, 1))
            QTest.qWait(280)
            self.assertEqual(w.current_state, 'Hover')
            self.assertTrue(w.dashboard.isVisible())
            QTest.keyClick(w.nav_buttons[0], Qt.Key.Key_Escape)
            self.assertEqual(w.current_state, 'Hidden')
            QTest.qWait(280)
            QTest.mouseClick(w.island_root, Qt.MouseButton.LeftButton,
                             pos=QPoint(w.island_root.width() // 2, 1))
            QTest.qWait(280)
            with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
                w.check_mouse_position()
            self.assertEqual(w.current_state, 'Hidden')

    def test_notifications_do_not_expand_closed_browser_panel(self):
        w = self.browser_window()
        w.check_mouse_position()
        w.show_notification('Test', 'Title', 'Body')
        w.trigger_charging_anim()
        self.assertEqual(w.current_state, 'Hidden')
        self.assertFalse(w.is_charging)

    def test_editor_stays_open_when_pointer_leaves(self):
        w = self.browser_window()
        w.check_mouse_position()
        QTest.qWait(280)
        QTest.mouseClick(w.island_root, Qt.MouseButton.LeftButton,
                         pos=QPoint(w.island_root.width() // 2, 1))
        w.is_editing_tasks = True
        with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
            w.check_mouse_position()
        self.assertEqual(w.current_state, 'Hover')
        w.is_editing_tasks = False

    def test_detector_remembers_browser_while_daisy_has_focus(self):
        import os
        import psutil
        from browser_behavior import BrowserGuard
        pid, now = [42], [0]
        names = {42: 'brave.exe', 43: 'notepad.exe'}
        guard = BrowserGuard(foreground_pid=lambda: pid[0],
                             process_name=lambda p: names[p], clock=lambda: now[0])
        self.assertTrue(guard.is_active())
        pid[0] = os.getpid()
        self.assertTrue(guard.is_active())
        pid[0] = 43
        self.assertFalse(guard.is_active())
        pid[0] = os.getpid()
        self.assertFalse(guard.is_active())
        for name in ('chrome.exe', 'msedge.exe', 'firefox.exe', 'opera.exe', 'vivaldi.exe', 'arc.exe'):
            pid[0] = 42
            names[42] = name
            now[0] += 3
            self.assertTrue(guard.is_active())
        def denied(_):
            raise psutil.AccessDenied(42)
        guard.process_name = denied
        now[0] += 3
        self.assertFalse(guard.is_active())
    def test_desktop_restores_normal_clock_and_hover(self):
        w = self.browser_window()
        w.check_mouse_position()
        w.browser_guard = SimpleNamespace(is_active=lambda: False)
        with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
            w.check_mouse_position()
        self.assertEqual(w.current_state, 'Idle')
        QTest.qWait(280)
        with patch.object(main.QCursor, 'pos', return_value=w.mapToGlobal(w.get_island_rect().center().toPoint())):
            w.check_mouse_position()
        self.assertEqual(w.current_state, 'Hover')
