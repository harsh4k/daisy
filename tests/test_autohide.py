"""Native island state integration for local Daisy inactivity."""
import json
import unittest
from unittest.mock import patch
from PyQt6.QtCore import QPoint
import test_hover
import settle


class AutoHideTests(unittest.TestCase):
    def window(self, config=None):
        fixture = test_hover.HoverTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.window(config)

    def test_hidden_line_is_solid_black_in_all_themes(self):
        from theme_tokens import THEMES
        w = self.window()
        w.change_state('Hidden')
        test_hover.QTest.qWait(280)
        for theme in THEMES:
            w.set_theme(theme)
            test_hover.APP.processEvents()
            center = w.get_island_rect().center().toPoint()
            pixel = w.grab().toImage().pixelColor(center)
            self.assertEqual(pixel.getRgb(), (0, 0, 0, 255), theme)

    def test_defaults_and_malformed_preferences(self):
        for config in ({}, {'autohide_delay': [], 'idle_icon': [], 'custom_idle_icon': None},
                       {'autohide_delay': True, 'idle_icon': 'missing'}):
            w = self.window(config)
            self.assertEqual(w.settings.get('autohide_delay'), 10)
            # Missing or invalid choices fall back to the redesign's Aurora orb.
            self.assertEqual(w.settings.get('idle_icon'), 'Aurora')
            self.assertIsInstance(w.settings.get('custom_idle_icon'), str)

    def test_hidden_line_and_restore_for_every_shell(self):
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w = self.window({'island_style': style})
            w.change_state('Hidden')
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual((w.island_w, w.island_h), (96, 4))
            self.assertEqual(w.get_island_rect().y(), 0)
            self.assertTrue(w.content_container.isHidden())
            top = w.mapToGlobal(w.get_island_rect().center().toPoint())
            with patch.object(test_hover.main.QCursor, 'pos', return_value=top):
                w.check_mouse_position()
            test_hover.QTest.qWait(280)
            self.assertEqual(w.current_state, 'Hover')
            self.assertFalse(w.content_container.isHidden())

    def test_ten_seconds_without_daisy_interaction_hides(self):
        from idle_behavior import IdleBehavior
        w = self.window()
        elapsed = [0.]
        w.idle_behavior = IdleBehavior(clock=lambda: elapsed[0])
        with patch.object(test_hover.main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
            elapsed[0] = 9.99
            w.check_mouse_position()
            self.assertEqual(w.current_state, 'Idle')
            elapsed[0] = 10.
            w.check_mouse_position()
            self.assertEqual(w.current_state, 'Hidden')

    def test_notification_interrupts_hidden_then_returns_to_clock(self):
        w = self.window()
        w.change_state('Hidden')
        test_hover.QTest.qWait(280)
        w.show_notification('Messages', 'Title', 'Body')
        # The porcelain card drops in after the island swells; wait for rest.
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Notify')
        self.assertFalse(w.notification_banner.isHidden())
        self.assertFalse(w.content_container.isHidden())
        w.revert_timer.stop()
        w.revert_timer.timeout.emit()
        test_hover.QTest.qWait(280)
        self.assertEqual(w.current_state, 'Idle')
        self.assertIn(':', w.status_text.text())

    def test_disabling_auto_hide_restores_idle_and_persists(self):
        w = self.window()
        w.change_state('Hidden')
        test_hover.QTest.qWait(280)
        with patch.object(w, 'has_keyboard_focus', return_value=True):
            w.set_autohide_delay(0)
        self.assertEqual(w.current_state, 'Idle')
        self.assertEqual(w.idle_behavior.timeout, 0)
        with open(w.config_path) as stream:
            self.assertEqual(json.load(stream)['autohide_delay'], 0)

    def test_charging_wakes_hidden_without_painting_an_accent_rectangle(self):
        w = self.window()
        w.change_state('Hidden')
        test_hover.QTest.qWait(280)
        w.trigger_charging_anim()
        test_hover.QTest.qWait(280)
        self.assertEqual(w.current_state, 'Idle')
        self.assertTrue(w.is_charging)
        self.assertFalse(w.content_container.isHidden())
        w.charging_anim.stop()
        w.cleanup_charging_anim()

    def test_icon_selection_persists_and_notification_pauses_animation(self):
        w = self.window()
        w.set_idle_icon('Orbit')
        with open(w.config_path) as stream:
            self.assertEqual(json.load(stream)['idle_icon'], 'Orbit')
        w.show_notification('Messages', 'Title', 'Body')
        self.assertEqual(w.current_state, 'Notify')
        self.assertFalse(w.status_icon.loop_timer.isActive())
        self.assertFalse(w.set_idle_icon('Custom GIF', 'missing-animation.gif'))
        self.assertEqual(w.settings['idle_icon'], 'Orbit')


if __name__ == '__main__':
    unittest.main()
