"""Feature content uses the shared card instead of narrow legacy columns."""
import unittest

from PyQt6.QtWidgets import QApplication, QPushButton, QLabel
from PyQt6.QtCore import QPoint, QRect
import test_hover
import settle


class CardCompositionTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_editor_resets_long_list_scroll_before_showing_fields(self):
        tasks = [dict(name=f'Task {i}', time='12:00', category='Work') for i in range(20)]
        w = self.window({'motion_mode': 'reduced', 'tasks': tasks})
        w.select_feature('calendar')
        QApplication.processEvents()
        # The card keeps its size, so the long list scrolls inside it.
        self.assertEqual(w.calendar_panel.height(), 208)
        self.assertEqual(w.feature_scroll.verticalScrollBar().maximum(), 0)
        bar = w.tasks_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.assertGreater(bar.value(), 0)
        w.open_task_editor()
        QApplication.processEvents()
        viewport = w.feature_scroll.viewport()
        self.assertEqual(w.tasks_scroll.verticalScrollBar().value(), 0)
        self.assertEqual(w.calendar_panel.height(), 208)
        for control in (w.edit_name, w.edit_time, w.edit_cat):
            self.assertTrue(viewport.rect().contains(QRect(control.mapTo(viewport, QPoint()), control.size())))

    def test_weather_tasks_and_calendar_use_full_content_width(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        for name, panel in [('weather', w.weather_panel), ('calendar', w.calendar_panel),
                            ('month', w.month_panel)]:
            w.select_feature(name)
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(panel.width(), w.feature_scroll.viewport().width(), name)
            self.assertEqual(w.feature_scroll.horizontalScrollBar().maximum(), 0)

    def test_task_editor_actions_fit_without_outer_scrolling(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        w.select_feature('calendar')
        w.open_task_editor()
        self.assertTrue(settle.settle_shell(w))
        QApplication.processEvents()
        self.assertEqual(w.calendar_panel.height(), 208)
        self.assertEqual(w.feature_scroll.verticalScrollBar().maximum(), 0)
        for button in w.task_edit_widget.findChildren(QPushButton):
            self.assertTrue(w.task_edit_widget.rect().contains(
                button.geometry().translated(button.parentWidget().mapTo(w.task_edit_widget, button.parentWidget().rect().topLeft()))), button.text())

    def test_month_shows_today_large_beside_a_painted_month(self):
        import datetime
        from PyQt6.QtGui import QColor
        w = self.window({'motion_mode': 'reduced'})
        today = datetime.date.today()
        page = w.calendar_page
        self.assertIs(w.month_panel, page)
        self.assertEqual(page.day.text(), str(today.day))
        self.assertEqual(page.weekday.text(), today.strftime('%A'))
        self.assertEqual(page.month.text(), today.strftime('%B %Y'))
        self.assertIn(today.strftime('%B %Y'), page.grid.accessibleName())
        page.grid.resize(360, 160)
        image = page.grid.grab().toImage()
        painted = {image.pixelColor(x, y).rgba() for x in range(0, image.width(), 6) for y in range(0, image.height(), 6)}
        self.assertGreater(len(painted), 2, 'the weekday letters and day numbers are drawn')
