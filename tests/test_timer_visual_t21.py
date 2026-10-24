"""Reference timer composition keeps durations honest and controls reachable."""
import unittest
from PyQt6.QtCore import QPoint, QRect
import test_hover
from tools_panel import ToolsPanel
from theme_tokens import get_theme


class TimerVisualTests(unittest.TestCase):
    def test_duration_ruler_tracks_custom_duration_without_restarting_session(self):
        panel = ToolsPanel([])
        self.addCleanup(panel.close)
        self.assertTrue(hasattr(panel, 'duration_ruler'), 'Timer needs a duration ruler')
        for minutes in (1, 17, 180):
            panel.minutes.setValue(minutes)
            self.assertEqual(panel.duration_ruler.minutes, minutes)
            self.assertEqual(panel.time_text.text(), f'{minutes:02d}:00')
        panel.start(25)
        deadline = panel.timer._deadline
        panel.minutes.setValue(17)
        self.assertEqual(panel.timer._deadline, deadline)
        self.assertEqual(panel.timer.state, 'running')

    def test_amber_clock_and_ruler_fit_above_aligned_transport_at_compact_width(self):
        panel = ToolsPanel([])
        self.addCleanup(panel.close)
        panel.resize(500, 208)
        panel.show()
        test_hover.APP.processEvents()
        self.assertIn('timer_accent', get_theme())
        self.assertTrue(hasattr(panel, 'duration_ruler'), 'Timer needs a duration ruler')
        bounds = lambda child: QRect(child.mapTo(panel, QPoint()), child.size())
        self.assertLess(bounds(panel.duration_ruler).bottom(), bounds(panel.time_text).top())
        for button in (panel.start_button, panel.pause_button, panel.reset_button):
            self.assertGreaterEqual(button.width(), 32)
            self.assertGreaterEqual(button.height(), 32)
            self.assertFalse(button.icon().isNull())
            self.assertTrue(panel.rect().contains(bounds(button)))
        self.assertEqual(bounds(panel.time_text).right(), bounds(panel.state_text).right())
