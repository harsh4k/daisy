import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import QObject, pyqtProperty
from PyQt6.QtTest import QTest
import test_hover
import settle
APP = test_hover.APP

class MotionPolicyTests(unittest.TestCase):
    def test_auto_reads_system_and_explicit_modes_override(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('motion_policy'), 'Shared reduced motion policy is missing')
        from motion_policy import effective_reduced_motion
        with patch('motion_policy.windows_animations_enabled', return_value=False):
            self.assertTrue(effective_reduced_motion('auto'))
            self.assertFalse(effective_reduced_motion('full'))
            self.assertTrue(effective_reduced_motion('reduced'))
        with patch('motion_policy.windows_animations_enabled', return_value=None):
            self.assertFalse(effective_reduced_motion('auto'))

class VisualShellTests(unittest.TestCase):
    window = test_hover.HoverTests.window
    def test_startup_compact_content_is_fully_opaque(self):
        w = self.window({'motion_mode': 'full'})
        self.assertEqual(w.content_opacity.opacity(), 1.)

    def test_single_named_power_menu_replaces_unlabelled_actions(self):
        w = self.window()
        self.assertEqual(len(w.power_buttons), 1)
        self.assertEqual([a.text() for a in w.power_buttons[0].menu().actions()], ['Sleep', 'Restart PC', 'Shut down'])

    def test_reduced_motion_applies_immediately_and_stops_loops(self):
        w = self.window({'motion_mode':'reduced', 'idle_icon':'Daisy', 'decorative_effects_enabled':True})
        self.assertTrue(hasattr(w, 'apply_visual_preferences'))
        w.change_state('Hover')
        self.assertEqual((w.island_w, w.island_h), (624, 272))
        self.assertFalse(w.anim_timer.isActive())
        self.assertFalse(w.status_icon.loop_timer.isActive())
        self.assertEqual(w.settings['idle_icon'], 'Daisy')

    def test_repeated_target_does_not_restart_and_interruptions_settle(self):
        w = self.window({'motion_mode':'full'})
        w.change_state('Hover')
        QTest.qWait(100)
        before = w.anim_group.currentTime()
        w.execute_liquid_transition()
        self.assertGreaterEqual(w.anim_group.currentTime(), before)
        w.select_feature('weather')
        QTest.qWait(30)
        w.select_feature('tools')
        QTest.qWait(30)
        w.select_feature('dashboard')
        QTest.qWait(400)
        self.assertFalse(w.dashboard.isHidden())
        self.assertTrue(w.weather_panel.isHidden())
        self.assertTrue(w.tools_panel.isHidden())
        self.assertEqual(w.content_opacity.opacity(), 1.)

    def test_quiet_default_preserves_selected_background_effect(self):
        w = self.window({'animation_style':'Fluid Blobs'})
        self.assertFalse(w.settings.get('decorative_effects_enabled', True))
        self.assertFalse(w.anim_timer.isActive())
        self.assertEqual(w.animation_style, 'Fluid Blobs')


    def test_resume_after_game_interrupts_collapse_settles_clock(self):
        import types
        from PyQt6.QtCore import QPoint
        w = self.window({'motion_mode':'full'})
        w.change_state('Hover')
        settle.settle_shell(w)
        if APP.focusWidget(): APP.focusWidget().clearFocus()
        w.change_state('Idle')
        QTest.qWait(110)
        w.game_guard = types.SimpleNamespace(is_active=lambda:True)
        w.check_mouse_position()
        w.game_guard = types.SimpleNamespace(is_active=lambda:False)
        with patch.object(test_hover.main.QCursor, 'pos', return_value=QPoint(-1000,-1000)):
            w.check_mouse_position()
        settle.settle_shell(w)
        self.assertEqual((w.island_w,w.island_h),(180,40))
        self.assertEqual(w.content_opacity.opacity(),1.)
        self.assertFalse(w.content_container.isHidden())

    def test_theme_action_updates_live_and_saved_selection(self):
        import json
        w = self.window()
        w.set_theme('Amethyst')
        self.assertEqual(w.theme['name'],'Amethyst')
        with open(w.config_path,encoding='utf-8') as stream:
            self.assertEqual(json.load(stream)['theme'],'Amethyst')
