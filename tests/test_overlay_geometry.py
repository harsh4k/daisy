"""Startup and native-window bounds, before a hover can repair stale geometry."""
import unittest
import datetime
from PyQt6.QtCore import QPoint, QRect
import test_hover


class OverlayGeometryTests(unittest.TestCase):
    def window(self, config):
        fixture = test_hover.HoverTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.window(config)

    def test_compact_clock_group_is_centered_on_both_axes(self):
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w = self.window({'island_style': style})
            for hour in (1, 11, 23):
                fixed = datetime.datetime(2026, 10, 21, hour, 59)
                with test_hover.patch.object(test_hover.main.datetime, 'datetime') as clock:
                    clock.now.return_value = fixed
                    w.update_content()
                test_hover.APP.processEvents()
                icon = QRect(w.status_icon.mapTo(w, QPoint()), w.status_icon.size())
                text = QRect(w.status_text.mapTo(w, QPoint()), w.status_text.size())
                group = icon.united(text).united(QRect(w.trailing_slot.mapTo(w, QPoint()), w.trailing_slot.size()))  # leading slot, clock, trailing slot
                shell = w.get_island_rect()
                self.assertLessEqual(abs(group.center().x() - shell.center().x()), 1)
                self.assertLessEqual(abs(group.center().y() - shell.center().y()), 1)
                self.assertTrue(shell.toAlignedRect().contains(group))

    def test_clock_starts_inside_shell_without_hover_in_each_window_mode(self):
        for compatibility in (False, True):
            for style in ('Default', 'Liquid Glass', 'Notch Nook'):
                with self.subTest(compatibility=compatibility, style=style):
                    w = self.window({'compatibility_mode': compatibility, 'island_style': style})
                    test_hover.APP.processEvents()
                    shell = w.get_island_rect().toAlignedRect()
                    self.assertEqual(w.current_state, 'Idle')
                    self.assertEqual(w.island_root.geometry(), shell)
                    text = QRect(w.status_text.mapTo(w, QPoint()), w.status_text.size())
                    self.assertTrue(shell.contains(text), (shell, text))

    def test_native_host_rounding_is_disabled_when_shown(self):
        for compatibility in (False, True):
            with test_hover.patch.object(test_hover.main.ctypes.windll.dwmapi,
                                        'DwmSetWindowAttribute', return_value=0) as native:
                w = self.window({'compatibility_mode': compatibility})
                calls = [call for call in native.call_args_list if call.args[1] == 33]
                self.assertTrue(calls, 'Disable native rounding of the transparent host HWND')
                hwnd, attribute, preference, size = calls[-1].args
                self.assertEqual(hwnd.value, int(w.winId()))
                self.assertEqual(preference._obj.value, 1)
                self.assertEqual(size, 4)

    def test_recenter_realigns_children_after_available_screen_changes(self):
        w = self.window({'compatibility_mode': False})
        screen = test_hover.types.SimpleNamespace(availableGeometry=lambda: QRect(-900, 80, 900, 650))
        with test_hover.patch.object(w, 'screen', return_value=screen):
            w.recenter_window()
            self.assertEqual(w.island_root.geometry(), w.get_island_rect().toAlignedRect())
            w.compatibility_mode = True
            w.recenter_window()
            self.assertEqual(w.island_root.geometry(), w.get_island_rect().toAlignedRect())


if __name__ == '__main__':
    unittest.main()
