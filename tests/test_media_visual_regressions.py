"""Rendered empty media state and coordinated page-swap regressions."""
import unittest
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
import test_hover


class MediaVisualRegressionTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_seek_rail_has_an_accessible_hit_area(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        self.assertGreaterEqual(w.dashboard.progress.height(), 32)

    def test_empty_seek_rail_does_not_fill_its_interaction_rectangle(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        test_hover.APP.processEvents()
        image = w.dashboard.progress.grab().toImage()
        scale = image.devicePixelRatio()
        pixel = image.pixelColor(round(image.width() / 2), round(2 * scale))
        background = QColor(w.theme['background'])
        self.assertLess(max(abs(pixel.red() - background.red()),
                            abs(pixel.green() - background.green()),
                            abs(pixel.blue() - background.blue())), 12)

    def test_media_update_cannot_bypass_page_fade_out(self):
        w = self.window({'motion_mode': 'full'})
        w.change_state('Hover')
        QTest.qWait(300)
        w.select_feature('weather')
        self.assertFalse(w.dashboard.isHidden())
        self.assertTrue(w.weather_panel.isHidden())
        w.update_media('Idle', '', '', '')
        self.assertFalse(w.dashboard.isHidden())
        self.assertTrue(w.weather_panel.isHidden())
        QTest.qWait(200)
        self.assertTrue(w.dashboard.isHidden())
        self.assertFalse(w.weather_panel.isHidden())
