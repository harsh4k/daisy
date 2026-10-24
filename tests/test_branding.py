import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import hashlib
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontInfo, QIcon

APP = QApplication.instance() or QApplication([])

class BrandingTests(unittest.TestCase):
    def test_provider_icons_match_unmodified_publisher_assets(self):
        from branding import media_icon, resource_path
        directory = Path(resource_path('assets/provider-icons'))
        manifest = directory / 'sources.json'
        self.assertTrue(manifest.is_file(), 'Real publisher icon provenance is missing')
        sources = json.loads(manifest.read_text(encoding='utf-8'))
        for kind, source, title in [('spotify', 'Spotify', 'Track'),
                                    ('netflix', 'Chrome.exe', 'Netflix'),
                                    ('youtube', 'YouTube', 'Video'),
                                    ('chrome', 'Chrome.exe', 'Video'),
                                    ('edge', 'msedge.exe', 'Video'),
                                    ('brave', 'Brave.exe', 'Video')]:
            with self.subTest(kind=kind):
                self.assertIn(kind, sources, 'Publisher asset is missing')
                asset = directory / sources[kind]['file']
                self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), sources[kind]['sha256'])
                expected = QIcon(str(asset))
                for size in (20, 32, 76, 128):
                    image = media_icon(source, title, size).pixmap(size, size).toImage()
                    self.assertFalse(image.isNull())
                    self.assertEqual(image, expected.pixmap(size, size).toImage())

    def test_provider_identity_uses_source_or_netflix_title(self):
        from branding import media_identity
        self.assertEqual(media_identity('SpotifyAB.SpotifyMusic_xyz!Spotify', 'Track'), ('Spotify', 'spotify'))
        self.assertEqual(media_identity('Spotify.exe', 'Netflix & Chill'), ('Spotify', 'spotify'))
        self.assertEqual(media_identity('YouTube', 'Netflix trailer'), ('YouTube', 'youtube'))
        self.assertEqual(media_identity('Chrome.exe', 'Netflix'), ('Netflix', 'netflix'))
        self.assertEqual(media_identity('com.netflix.app', 'Episode'), ('Netflix', 'netflix'))
        self.assertEqual(media_identity('Chrome.exe', 'YouTube'), ('YouTube', 'youtube'))
        self.assertEqual(media_identity('Chrome.exe', 'Some video'), ('Browser', 'browser'))
        self.assertEqual(media_identity('', ''), ('Media', 'media'))

    def test_known_service_icons_render_at_small_and_cover_sizes(self):
        from branding import media_icon
        for source, title in [('Spotify', 'Track'), ('Chrome.exe', 'Netflix'), ('YouTube', 'Video')]:
            for size in (20, 32, 76):
                icon = media_icon(source, title, size)
                self.assertFalse(icon.isNull())
                image = icon.pixmap(size, size).toImage()
                self.assertFalse(image.isNull())
                self.assertTrue(any(image.pixelColor(x, y).alpha() for x in range(size) for y in range(size)))

    def test_runtime_font_matches_preview_font_instead_of_serif_fallback(self):
        from app_runtime import configure_application
        configure_application(APP)
        actual = QFontInfo(APP.font()).family()
        self.assertIn('Inter', actual)

if __name__ == '__main__':
    unittest.main()
