import unittest
import datetime
from unittest.mock import patch
from PyQt6.QtCore import Qt
import test_hover


class AnimationTests(unittest.TestCase):
    def window(self):
        fixture = test_hover.HoverTests('test_hover_dashboard_survives_rapid_reversal_without_text_drift')
        self.addCleanup(fixture.doCleanups)
        return fixture.window()

    def test_background_animation_menu_options_reach_dashboard(self):
        w = self.window()
        w.settings['motion_mode'] = 'full'
        # Decorative effects are an explicit opt-in, not a side effect of a menu pick.
        w.settings['decorative_effects_enabled'] = True
        w.current_state = 'Hover'
        w.current_feature_index = w.features.index('dashboard')
        w.media_state = 'Playing'
        w.execute_liquid_transition()
        test_hover.QTest.qWait(300)
        for style in ('Glow Sweep', 'Fluid Blobs', 'Neon Border'):
            w.set_animation_style(style)
            w.gradient_phase = 0.
            before = w.grab().toImage()
            w.gradient_phase = .3
            after = w.grab().toImage()
            self.assertNotEqual(before, after, style + ' must visibly animate the dashboard')
        w.set_animation_style('None')
        w.gradient_phase = 0.
        before = w.grab().toImage()
        w.gradient_phase = .3
        self.assertEqual(before, w.grab().toImage())
    def test_compact_clock_survives_playback_and_lyrics(self):
        w = self.window()
        fixed = datetime.datetime(2026, 10, 20, 14, 7)
        with patch.object(test_hover.main.datetime, 'datetime') as clock:
            clock.now.return_value = fixed
            for state in ('Playing', 'Paused', 'Idle'):
                w.update_media(state, 'Netflix', 'Artist', '')
                w.update_lyrics('A lyric line')
                w.update_content()
                self.assertEqual(w.status_text.text(), 'Tue 2:07 PM')

    def test_background_menu_never_rewrites_the_decorative_preference(self):
        w = self.window()
        w.settings['motion_mode'] = 'full'
        w.settings['decorative_effects_enabled'] = False
        w.set_animation_style('Glow Sweep')
        self.assertFalse(w.settings['decorative_effects_enabled'])
        self.assertEqual(w.settings['animation_style'], 'Glow Sweep')
        self.assertFalse(w.decorative_motion)

if __name__ == '__main__':
    unittest.main()


