import importlib.util
import os
import unittest
from pathlib import Path
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt, QPoint, QRect, QCoreApplication, QEvent

APP = QApplication.instance() or QApplication([])

class DashboardTests(unittest.TestCase):
    def panel(self):
        self.assertIsNotNone(importlib.util.find_spec('dashboard_panel'), 'Hover dashboard must exist')
        from dashboard_panel import DashboardPanel
        p = DashboardPanel()
        p.show()
        APP.processEvents()
        def dispose():
            p.close()
            p.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            APP.processEvents()
        self.addCleanup(dispose)
        return p

    def test_system_readout_lives_in_its_own_card(self):
        from system_card import SystemCard
        card = SystemCard()
        card.update_metrics({'cpu': 34, 'ram': 61, 'disk': 78, 'down': 2048, 'up': 1024})
        self.assertEqual(card.metric_values['cpu'].text(), '34%')
        self.assertEqual(card.metric_values['ram'].text(), '61%')
        self.assertIn('2 KB/s', card.network.text())
        card.deleteLater()

    def test_music_and_glances_fit_side_by_side(self):
        p = self.panel()
        p.update_media('Playing', 'A very long track title ' * 15, 'Long artist ' * 15, '')
        p.update_timeline(63, 240)
        p.set_glance('tools', 'Focus', 'Ready · 25 min', '25:00')
        APP.processEvents()
        self.assertEqual(p.elapsed.text(), '1:03')
        self.assertEqual(p.duration.text(), '4:00')
        self.assertTrue(p.rect().contains(p.glance_column.geometry()))
        self.assertTrue(p.rect().contains(p.media_card.geometry()))
        self.assertFalse(p.glance_column.geometry().intersects(p.media_card.geometry()))
        self.assertGreater(p.glance_column.x(), p.media_card.x(), 'music leads, glances sit to its right')
        for button in p.glances.values():
            bounds = QRect(button.mapTo(p, QPoint()), button.size())
            self.assertTrue(p.rect().contains(bounds), button.key)
        self.assertLessEqual(p.title.width(), p.media_card.width())
        self.assertEqual(p.title.toolTip(), 'A very long track title ' * 15)

    def test_empty_media_clears_timeline_and_disables_transport(self):
        p = self.panel()
        p.update_media('Playing', 'Track', 'Artist', '')
        p.update_timeline(63, 240)
        p.update_media('Idle', '', '', '')
        self.assertEqual(p.progress.value(), 0)
        self.assertEqual(p.elapsed.text(), '0:00')
        self.assertFalse(p.play.isEnabled())
        self.assertFalse(p.artwork.pixmap().isNull())

    def test_media_reference_alignment_and_provider_badge(self):
        p = self.panel()
        p.update_source('Chrome.exe')
        p.update_media('Playing', 'Netflix', '', '')
        p.update_artwork(Path('assets/daisy.png').read_bytes())
        APP.processEvents()
        self.assertEqual(p.source.text(), 'Netflix')
        self.assertFalse(p.source_badge.isHidden())
        self.assertFalse(p.source_badge.pixmap().isNull())
        with_badge = p.artwork.grab().toImage()
        p.source_badge.hide()
        without_badge = p.artwork.grab().toImage()
        self.assertNotEqual(with_badge, without_badge, 'Provider badge must render over the artwork')
        p.source_badge.show()
        self.assertFalse(p.artwork.pixmap().isNull())
        from dashboard_panel import ART
        self.assertEqual(p.artwork.width(), ART)
        self.assertGreater(p.play.height(), p.prev.height())
        self.assertGreater(p.prev.geometry().top(), p.duration.geometry().bottom())
        self.assertEqual(p.title.x(), p.artist.x())
        self.assertLessEqual(p.title.geometry().bottom(), p.artist.geometry().top())

    def test_fallback_logo_has_no_duplicate_provider_badge(self):
        p = self.panel()
        p.update_source('Brave')
        p.update_media('Playing', 'Netflix', '', '')
        for data in (b'', b'invalid cover'):
            p.update_artwork(data)
            self.assertTrue(p.source_badge.isHidden())
            self.assertFalse(p.artwork.pixmap().isNull())
            p.update_source('Brave')
            self.assertTrue(p.source_badge.isHidden())
        p.update_artwork(Path('assets/daisy.png').read_bytes())
        self.assertFalse(p.source_badge.isHidden())
        p.update_artwork(b'')
        self.assertTrue(p.source_badge.isHidden())

    def test_every_theme_is_applied_without_media_accent_overwrite(self):
        p = self.panel()
        from theme_tokens import THEMES, get_theme
        self.assertEqual(set(THEMES), {'Dark Matter', 'Graphite', 'Amethyst', 'Midnight', 'Rose'})
        for name in THEMES:
            theme = get_theme(name)
            p.set_theme(theme)
            before = p.styleSheet()
            p.update_media('Paused', 'Track', 'Artist', '#00ff00')
            self.assertEqual(p.styleSheet(), before)
            self.assertIn(theme['accent'], before)
        self.assertEqual(get_theme('bad')['name'], 'Dark Matter')

    def test_reference_geometry_fits_normal_and_small_width_in_all_themes(self):
        from theme_tokens import THEMES, get_theme
        p = self.panel()
        for width in (592, 468):
            p.set_available_width(width)
            for name in THEMES:
                p.set_theme(get_theme(name))
                p.update_media('Paused', 'A long title ' * 20, 'An artist ' * 20, '')
                p.update_source('Spotify')
                APP.processEvents()
                for widget in (p.artwork, p.title, p.artist, p.progress, p.elapsed,
                               p.duration, p.prev, p.play, p.next):
                    bounds = QRect(widget.mapTo(p, QPoint()), widget.size())
                    self.assertTrue(p.rect().contains(bounds), (width, name, widget.objectName()))
                self.assertEqual(p.elapsed.y(), p.duration.y())
                self.assertLessEqual(p.title.fontMetrics().horizontalAdvance(p.title.text()), p.title.width())
                self.assertLessEqual(p.artist.fontMetrics().horizontalAdvance(p.artist.text()), p.artist.width())

    def test_transport_icons_remain_visible_when_playback_changes(self):
        p = self.panel()
        for state in ('Playing', 'Paused', 'Idle'):
            p.update_media(state, 'Track' if state != 'Idle' else '', 'Artist', '')
            for button in (p.prev, p.play, p.next):
                self.assertFalse(button.icon().isNull())

if __name__ == '__main__':
    unittest.main()
