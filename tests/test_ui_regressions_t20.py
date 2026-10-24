"""Reported Tasks background, timer controls and compact clock regressions."""
import unittest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QAbstractSpinBox
import test_hover


class UiRegressionTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_task_scroll_does_not_fill_with_default_system_palette(self):
        w = self.window({'motion_mode': 'reduced'})
        w.select_feature('calendar')
        QApplication.processEvents()
        for child in (w.tasks_scroll.viewport(), w.tasks_container_widget):
            self.assertFalse(child.autoFillBackground())
        image = w.grab().toImage()
        viewport = w.tasks_scroll.viewport()
        sample = viewport.mapTo(w, viewport.rect().bottomRight() - QPoint(2, 2))
        ratio = image.devicePixelRatio()
        pixel = image.pixelColor(round(sample.x() * ratio), round(sample.y() * ratio))
        # Transparent scroll areas show the island fill, never the system palette.
        self.assertEqual(pixel, QColor(w.theme['island']), pixel.getRgb())

    def test_timer_presets_and_custom_minutes_are_clear_and_immediate(self):
        w = self.window({'motion_mode': 'reduced'})
        w.select_feature('tools')
        QApplication.processEvents()
        panel = w.tools_panel
        self.assertTrue(all(b.height() >= 32 for b in panel.preset_buttons))
        self.assertEqual(panel.minutes.buttonSymbols(), QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.assertEqual([b.text() for b in panel.preset_buttons], ['5 min', '15 min', '25 min', '50 min'])
        panel.minutes.setValue(15)
        self.assertEqual(panel.time_text.text(), '15:00')
        self.assertEqual([b.isChecked() for b in panel.preset_buttons], [False, True, False, False])
        panel.minutes.setValue(17)
        self.assertFalse(any(b.isChecked() for b in panel.preset_buttons))

    def test_plugged_battery_does_not_crop_idle_clock_in_any_shell(self):
        w = self.window({'motion_mode': 'reduced'})
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w.island_style = style
            w.change_state('Idle')
            w.publish_battery({'percent': 100, 'plugged': True, 'secsleft': 0})
            w.status_text.setText('Wed, 12:27 AM')
            w.header_layout.activate()
            QApplication.processEvents()
            self.assertFalse(w.battery_indicator.isVisible())
            self.assertGreaterEqual(w.status_text.width(), w.status_text.fontMetrics().horizontalAdvance(w.status_text.text()))
            icon = QRect(w.status_icon.mapTo(w, QPoint()), w.status_icon.size())
            text = QRect(w.status_text.mapTo(w, QPoint()), w.status_text.size())
            self.assertLessEqual(abs(icon.united(text).united(QRect(w.trailing_slot.mapTo(w, QPoint()), w.trailing_slot.size())).center().x() - w.get_island_rect().center().x()), 1)
