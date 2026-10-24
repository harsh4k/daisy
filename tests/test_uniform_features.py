"""Feature pages share one shell; longer content stays reachable by scrolling."""
import unittest
import types
from unittest.mock import patch

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QLabel

import test_hover
import settle


class UniformFeatureTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_all_features_and_editor_keep_overview_size(self):
        w = self.window({'motion_mode': 'reduced'})
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w.island_style = style
            w.change_state('Hover')
            for feature in w.features:
                w.select_feature(feature)
                self.assertTrue(settle.settle_shell(w))
                self.assertEqual((w.island_w, w.island_h), (624, 272), feature)
                self.assertTrue(w.content_container.rect().contains(w.navigation.geometry()))
            w.select_feature('calendar')
            w.open_task_editor()
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual((w.island_w, w.island_h), (624, 272))
            w.open_task_editor()

    def test_long_task_list_and_editor_scroll_without_changing_feature(self):
        tasks = [{'name': f'Task {i}', 'time': '12:00', 'category': 'Work'}
                 for i in range(20)]
        w = self.window({'tasks': tasks, 'motion_mode': 'reduced'})
        w.change_state('Hover')
        w.select_feature('calendar')
        self.assertTrue(settle.settle_shell(w))
        names = [label.text() for label in w.tasks_container_widget.findChildren(QLabel)]
        self.assertIn('Task 19', names)
        # The card keeps the overview size; the rows scroll inside it.
        from ui_tokens import SPACING
        # The page spans the shell between the macOS 20 px edge insets.
        self.assertEqual((w.calendar_panel_widget.width(), w.calendar_panel_widget.height()),
                         (624 - 2 * SPACING['outer'], 208))
        self.assertEqual(w.CALENDAR_H, 208)
        scroll = w.tasks_scroll
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        QApplication.processEvents()
        self.assertEqual(scroll.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.assertFalse(scroll.verticalScrollBar().isVisible())
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        index = w.current_feature_index
        point = QPointF(scroll.viewport().rect().center())
        event = QWheelEvent(point, QPointF(scroll.viewport().mapToGlobal(point.toPoint())),
                            QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(scroll.viewport(), event)
        self.assertEqual(w.current_feature_index, index)
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        for compatibility in (False, True):
            w.compatibility_mode = compatibility
            w.recenter_window()
            QApplication.processEvents()
            shell_point = QPointF(scroll.viewport().mapTo(w, point.toPoint()))
            bubbled = QWheelEvent(shell_point, QPointF(w.mapToGlobal(shell_point.toPoint())),
                                  QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
                                  Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
            w.wheelEvent(bubbled)
            self.assertEqual(w.current_feature_index, index)
        w.open_task_editor()
        self.assertTrue(settle.settle_shell(w))
        QApplication.processEvents()
        self.assertTrue(w.is_editing_tasks)
        self.assertEqual(w.calendar_panel_widget.height(), 208)
        self.assertEqual(w.edit_list.verticalScrollBarPolicy(),
                         Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        w.edit_name.setText('Added from fixed card')
        w.add_task_integrated()
        self.assertEqual(w.settings['tasks'][-1]['name'], 'Added from fixed card')
        w.save_and_close_editor()
        self.assertFalse(w.is_editing_tasks)
        self.assertEqual((w.island_w, w.island_h), (624, 272))

    def test_tools_primary_controls_fit_with_fixed_navigation(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        w.select_feature('tools')
        self.assertTrue(settle.settle_shell(w))
        for index in range(w.tools_panel.tabs.count()):
            w.tools_panel.tabs.setCurrentIndex(index)
            QApplication.processEvents()
            self.assertEqual(w.feature_scroll.verticalScrollBar().maximum(), 0)
            self.assertEqual(w.feature_scroll.horizontalScrollBar().maximum(), 0)
            from stage_bar import HEIGHT
            self.assertEqual(w.navigation.height(), HEIGHT)
            self.assertTrue(w.content_container.rect().contains(w.navigation.geometry()))

    def test_all_features_clamp_to_screen_without_horizontal_scrolling(self):
        w = self.window({'motion_mode': 'reduced'})
        screen = types.SimpleNamespace(availableGeometry=lambda: QRect(-500, 100, 500, 250))
        with patch.object(w, 'screen', return_value=screen):
            for style in ('Default', 'Liquid Glass', 'Notch Nook'):
                w.island_style = style
                w.change_state('Hover')
                for feature in w.features:
                    w.select_feature(feature)
                    self.assertTrue(settle.settle_shell(w))
                    QApplication.processEvents()
                    self.assertEqual(w.island_w, 500)
                    self.assertEqual(w.island_h, 250 if style == 'Notch Nook' else 240)
                    self.assertEqual(w.feature_scroll.horizontalScrollBar().maximum(), 0, feature)
                    self.assertTrue(w.content_container.rect().contains(w.navigation.geometry()))
