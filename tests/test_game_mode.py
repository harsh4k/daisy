"""Regression: a game's hidden cursor must never open the overlay."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint
from PyQt6.QtTest import QTest
import test_hover
import main


class GameModeTests(unittest.TestCase):
    window = test_hover.HoverTests.window
    def test_game_hides_overlay_even_with_cursor_over_pill(self):
        w = self.window({'idle_icon': 'Daisy'})
        w.game_guard = SimpleNamespace(is_active=lambda: True)
        pointer = w.mapToGlobal(w.get_island_rect().center().toPoint())
        with patch.object(main.QCursor, 'pos', return_value=pointer):
            w.check_mouse_position()
        self.assertFalse(w.isVisible(), 'Valorant must suppress the overlay entirely')
        self.assertNotEqual(w.current_state, 'Hover')
        w.update_content()
        self.assertFalse(w.status_icon.loop_timer.isActive())
        w.show_notification('Test', 'Title', 'Message')
        w.trigger_charging_anim()
        QTest.qWait(280)
        self.assertFalse(w.isVisible())
        self.assertFalse(w.status_icon.loop_timer.isActive())

    def test_alt_tab_restores_clock_and_normal_hover_for_all_shapes(self):
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w = self.window({'island_style': style})
            active = [True]
            w.game_guard = SimpleNamespace(is_active=lambda: active[0])
            w.check_mouse_position()
            self.assertFalse(w.isVisible())
            active[0] = False
            with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
                w.check_mouse_position()
            QTest.qWait(280)
            self.assertTrue(w.isVisible())
            self.assertEqual(w.current_state, 'Idle')
            self.assertIn(':', w.status_text.text())
            pointer = w.mapToGlobal(w.get_island_rect().center().toPoint())
            with patch.object(main.QCursor, 'pos', return_value=pointer):
                w.check_mouse_position()
            self.assertEqual(w.current_state, 'Hover')

    def test_detector_changes_with_foreground_and_recovers_from_access_denied(self):
        from game_mode import GameGuard
        import psutil
        now, pid = [0.0], [42]
        names = {42: 'VALORANT-Win64-Shipping.exe', 43: 'chrome.exe'}
        guard = GameGuard(foreground_pid=lambda: pid[0],
                          process_name=lambda p: names[p], clock=lambda: now[0])
        self.assertTrue(guard.is_active())
        pid[0] = 43
        self.assertFalse(guard.is_active())
        pid[0] = 42
        names[42] = 'VALORANT.exe'
        self.assertTrue(guard.is_active())
        def denied(_):
            raise psutil.AccessDenied(42)
        guard.process_name = denied
        now[0] = 3
        self.assertFalse(guard.is_active())
        guard.process_name = lambda _: 'VALORANT.exe'
        now[0] = 6
        self.assertTrue(guard.is_active())
        pid[0] = 0
        self.assertFalse(guard.is_active())
