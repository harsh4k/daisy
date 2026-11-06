import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontMetrics
from theme_tokens import get_theme
from dashboard_panel import DashboardPanel
APP = QApplication.instance() or QApplication([])

class VisualHierarchyTests(unittest.TestCase):
    def test_text_and_essential_boundaries_meet_contrast_thresholds(self):
        from theme_tokens import THEMES
        def luminance(color):
            values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
            return sum(a*b for a,b in zip(channels, (.2126, .7152, .0722)))
        def contrast(a, b):
            a, b = sorted((luminance(a), luminance(b)))
            return (b + .05) / (a + .05)
        for name in THEMES:
            for treatment in ('neutral', 'tinted'):
                t = get_theme(name, treatment)
                for surface in ('background', 'surface'):
                    for role in ('text', 'muted'):
                        self.assertGreaterEqual(contrast(t[role], t[surface]), 4.5, (name, treatment, role))
                    self.assertGreaterEqual(contrast(t['control_border'], t[surface]), 3.)
                    self.assertGreaterEqual(contrast(t['accent'], t[surface]), 3.)

    def test_theme_neutral_surface_preserves_only_selected_accent(self):
        neutral = get_theme('Amethyst')
        tinted = get_theme('Amethyst', 'tinted')
        self.assertEqual(neutral['background'], get_theme('Dark Matter')['background'])
        self.assertEqual(neutral['text'], get_theme('Dark Matter')['text'])
        self.assertEqual(neutral['accent'], tinted['accent'])
        self.assertNotEqual(neutral['background'], tinted['background'])
        self.assertIn('danger', neutral)

    def test_application_font_and_numeric_roles_are_stable(self):
        from branding import configure_fonts
        from ui_tokens import font
        configure_fonts(APP)
        self.assertEqual(APP.font().pixelSize(), 13)
        for role in ('time', 'compact', 'display'):
            metrics = QFontMetrics(font(role))
            widths = [metrics.horizontalAdvance(str(i) * 4) for i in range(10)]
            self.assertLessEqual(max(widths) - min(widths), 1, (role, widths))

    def test_source_configuration_is_hidden_but_feedback_keeps_its_space(self):
        panel = DashboardPanel()
        panel.show()
        APP.processEvents()
        self.addCleanup(panel.close)
        self.assertTrue(panel.source_picker.isHidden())
        before = panel.title.geometry()
        panel.show_transport_result('seek', False)
        APP.processEvents()
        self.assertTrue(panel.transport_status.isVisible())
        self.assertEqual(panel.title.geometry(), before)

    def test_elision_updates_when_font_changes_without_resize(self):
        from media_widgets import ElidedLabel
        label = ElidedLabel('A long title with words that need elision')
        label.resize(180, 28)
        label.show()
        APP.processEvents()
        label.setFont(QFont('Segoe UI', 28))
        APP.processEvents()
        self.addCleanup(label.close)
        self.assertLessEqual(label.fontMetrics().horizontalAdvance(label.text()), label.width())
        self.assertEqual(label.toolTip(), label.full_text)
