"""Compact tools retain every action within the uniform feature page."""
import unittest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import QPushButton
import test_hover
from tools_panel import ToolsPanel

class CompactToolsTests(unittest.TestCase):
    def panel(self, width=576):
        panel = ToolsPanel([])
        panel.resize(width, 208)
        panel.show()
        self.addCleanup(panel.close)
        test_hover.APP.processEvents()
        return panel

    def assert_inside(self, panel, child):
        bounds = QRect(child.mapTo(panel, QPoint()), child.size())
        self.assertTrue(panel.rect().contains(bounds), f'{child.accessibleName()}: {bounds}')

    def test_timer_all_actions_fit_without_scrolling(self):
        for width in (500, 576):
            panel = self.panel(width)
            self.assertLessEqual(panel.minimumSizeHint().height(), 208)
            for child in (panel.time_text, panel.state_text, panel.minutes,
                          panel.start_button, panel.pause_button, panel.reset_button):
                self.assert_inside(panel, child)
            for button in panel.tabs.widget(0).findChildren(QPushButton):
                self.assertGreaterEqual(button.height(), 32)
                self.assert_inside(panel, button)
            self.assert_inside(panel, panel.duration_ruler)
            clock = QRect(panel.time_text.mapTo(panel, QPoint()), panel.time_text.size())
            action = QRect(panel.start_button.mapTo(panel, QPoint()), panel.start_button.size())
            self.assertLess(action.right(), clock.left())
            self.assertLessEqual(abs(action.center().y() - clock.center().y()), 16)

    def test_shelf_toolbar_is_compact_and_accessible(self):
        panel = self.panel(500)
        panel.tabs.setCurrentIndex(1)
        test_hover.APP.processEvents()
        shelf = panel.shelf
        for button in shelf.findChildren(QPushButton):
            self.assertEqual(button.size().width(), 32)
            self.assertEqual(button.size().height(), 32)
            self.assertTrue(button.toolTip())
            self.assertTrue(button.accessibleName())
            self.assertFalse(button.icon().isNull())
            self.assert_inside(panel, button)
        self.assert_inside(panel, shelf.list)
        self.assertEqual(shelf.list.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_duration_and_transport_keep_timer_state(self):
        panel = self.panel()
        panel.minutes.setValue(15)
        panel.start_button.click()
        self.assertEqual(panel.timer.state, 'running')
        panel.pause_button.click()
        self.assertEqual(panel.timer.state, 'paused')
        panel.pause_button.click()
        self.assertEqual(panel.timer.state, 'running')
        panel.reset_button.click()
        self.assertEqual(panel.timer.state, 'idle')
