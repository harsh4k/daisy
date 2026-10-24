"""Regression tests for the approved visual hierarchy and motion design."""
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics
from PyQt6.QtTest import QTest

import settle
import test_hover

APP = test_hover.APP


class DesignTests(test_hover.HoverTests):
    """Covers the design decisions that had no proof yet."""

    def sample_opacity(self, window, duration=400):
        """Record the content opacity while the shell animates."""
        samples = []
        timer = QTimer(window)
        timer.setInterval(15)
        timer.timeout.connect(lambda: samples.append(window.content_opacity.opacity()))
        timer.start()
        QTest.qWait(duration)
        timer.stop()
        return samples

    def test_restoring_from_the_edge_line_reveals_content(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hidden')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Hidden')
        w.change_state('Idle')
        samples = self.sample_opacity(w, 320)
        self.assertTrue(any(0.0 < value < 1.0 for value in samples),
                        'restoring from the edge line must fade the content in')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.content_opacity.opacity(), 1.)

    def test_closing_to_the_edge_line_fades_content_first(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        w.change_state('Hidden')
        samples = self.sample_opacity(w, 120)
        self.assertTrue(any(0.0 < value < 1.0 for value in samples),
                        'the content must fade before the shell contracts')
        self.assertTrue(settle.settle_shell(w))

    def test_reduced_motion_shows_a_static_charging_state(self):
        w = self.window({'motion_mode': 'reduced'})
        w.trigger_charging_anim()
        self.assertTrue(w.is_charging)
        self.assertGreater(w.charging_phase, 0., 'reduced motion needs a visible charging state')
        self.assertFalse(w.charging_anim.state().value, 'reduced motion must not loop the charging pulse')
        self.assertTrue(settle.settle_shell(w))
        available = w.screen().availableGeometry().width()
        self.assertEqual(w.island_w, min(850, available))
        self.assertGreater(w.island_w, 180)

    def test_destructive_power_entries_use_the_danger_token(self):
        w = self.window()
        menu = w.power_buttons[0].menu()
        entries = {action.text(): action for action in menu.actions()}
        self.assertEqual(sorted(entries), ['Restart PC', 'Shut down', 'Sleep'])
        danger = QColor(w.theme['danger']).name()
        for label in ('Restart PC', 'Shut down'):
            image = entries[label].icon().pixmap(24, 24).toImage()
            colors = {image.pixelColor(x, y).name()
                      for x in range(image.width()) for y in range(image.height())
                      if image.pixelColor(x, y).alpha() > 200}
            self.assertIn(danger, colors, label + ' must carry the danger colour')
        sleep = entries['Sleep'].icon().pixmap(24, 24).toImage()
        sleep_colors = {sleep.pixelColor(x, y).name()
                        for x in range(sleep.width()) for y in range(sleep.height())
                        if sleep.pixelColor(x, y).alpha() > 200}
        self.assertNotIn(danger, sleep_colors, 'Sleep is not destructive')

    def test_destructive_buttons_use_the_danger_role(self):
        from file_shelf import FileShelf
        shelf = FileShelf([])
        self.assertEqual(shelf.remove_button.objectName(), 'DangerAction')
        from settings_rules_page import RulesPage
        page = RulesPage({}, lambda value: None)
        buttons = [button for button in page.findChildren(type(shelf.remove_button))
                   if button.objectName() == 'DangerAction']
        self.assertTrue(buttons, 'the rules page needs a destructive remove action')

    def test_numeric_roles_keep_equal_digit_advances(self):
        from ui_tokens import NUMERIC, font, font_css, stable_digits
        for role in NUMERIC:
            chosen = font(role)
            self.assertTrue(stable_digits(chosen), role)
            css = font_css(role)
            self.assertIn(chosen.family(), css, role)

    def test_rendered_numbers_do_not_shift_width(self):
        from ui_tokens import stable_digits
        w = self.window()
        labels = [w.status_text, w.cpu_label, w.ram_label,
                  w.dashboard.elapsed, w.dashboard.duration]
        labels += list(w.system_card.metric_values.values())
        labels += [w.net_down_L, w.net_up_L, w.tools_panel.time_text]
        for label in labels:
            metrics = QFontMetrics(label.font())
            widths = [metrics.horizontalAdvance(str(digit)) for digit in range(10)]
            self.assertLessEqual(max(widths) - min(widths), 1,
                                 '%s must not shift between digits' % label.objectName()
                                 or label.text())

    def test_expanded_features_keep_the_outer_margin(self):
        from ui_tokens import SPACING
        w = self.window()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.feature_scroll.pos().x(), SPACING['outer'])
        w.select_feature('weather')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.feature_scroll.pos().x(), SPACING['outer'])

    def test_hidden_header_transport_buttons_meet_the_target_size(self):
        w = self.window()
        for button in (w.btn_prev, w.btn_play, w.btn_next):
            self.assertGreaterEqual(button.width(), 32)
            self.assertGreaterEqual(button.height(), 32)
            self.assertTrue(button.toolTip())
            self.assertTrue(button.accessibleName())

    def test_invalid_custom_gif_is_not_read_again(self):
        w = self.window()
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, 'broken.gif')
        with open(path, 'wb') as stream:
            stream.write(b'not a gif')
        calls = []
        original = pathlib.Path.read_bytes

        def counted(self):
            calls.append(str(self))
            return original(self)

        with patch.object(pathlib.Path, 'read_bytes', counted):
            self.assertFalse(w.status_icon.set_style('Custom GIF', path))
            first = len(calls)
            self.assertGreater(first, 0)
            self.assertFalse(w.status_icon.set_style('Custom GIF', path))
            self.assertEqual(len(calls), first, 'a rejected GIF must not be read every second')

    def test_legacy_panels_use_tokens_instead_of_literal_colours(self):
        w = self.window()
        for panel in (w.weather_panel, w.calendar_panel, w.month_panel, w.perf_panel):
            for label in panel.findChildren(test_hover.main.QLabel):
                if not label.property('daisyTypeRole'):
                    continue
                style = label.styleSheet()
                self.assertNotIn('#888', style)
                self.assertNotIn('#AAA', style)
                self.assertNotIn('#00A0FF', style)


if __name__ == '__main__':
    unittest.main()
