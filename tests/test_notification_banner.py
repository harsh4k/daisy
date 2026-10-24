import unittest
from unittest.mock import patch
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtTest import QTest
import test_hover
import settle


class BannerTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_real_app_icon_tracks_sender_and_survives_theme_changes(self):
        from PyQt6.QtGui import QIcon
        from branding import resource_path
        from notification_banner import ICON_SIZE
        from theme_tokens import get_theme
        w = self.window({'motion_mode': 'reduced'})
        for sender, name in [('Codex', 'codex'), ('Claude', 'claude'), ('Claude Code', 'claude')]:
            w.show_notification(sender, 'Update', 'A notification')
            actual = w.notification_banner.icon.pixmap().toImage()
            original = QIcon(resource_path(f'assets/notification-icons/{name}.png')).pixmap(ICON_SIZE, ICON_SIZE).toImage()
            self.assertEqual(actual, original)
            w.notification_banner.set_theme(get_theme('Rose', 'tinted'))
            self.assertEqual(w.notification_banner.icon.pixmap().toImage(), original)
        w.show_notification('Unknown app', 'Codex mentioned in message', 'Claude')
        self.assertNotEqual(w.notification_banner.icon.pixmap().toImage(), original)

    def test_notification_has_separate_fields_and_dismisses(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Discord', 'A real title', 'A message with detail')
        test_hover.APP.processEvents()
        self.assertFalse(w.notification_banner.isHidden())
        self.assertTrue(w.header_widget.isHidden())
        banner = w.notification_banner
        self.assertEqual(banner.app.full_text, 'Discord')
        self.assertEqual(banner.title.full_text, 'A real title')
        self.assertEqual(banner.message.full_text, 'A message with detail')
        for child in (banner.app, banner.title, banner.message, banner.dismiss):
            self.assertTrue(banner.rect().contains(QRect(child.mapTo(banner, QPoint()), child.size())))
        banner.dismiss.click()
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Idle')

    def test_replacement_long_message_and_key_event_do_not_reuse_old_title(self):
        w = self.window({'motion_mode': 'reduced'})
        w.show_notification('Discord', 'Old', 'Old body')
        w.show_notification('WhatsApp', 'Long title ' * 30, 'Message ' * 50)
        test_hover.APP.processEvents()
        self.assertEqual(w.notification_banner.app.full_text, 'WhatsApp')
        self.assertLessEqual(w.notification_banner.title.fontMetrics().horizontalAdvance(
            w.notification_banner.title.text()), w.notification_banner.title.width())
        w.show_key_event('Caps Lock', True)
        self.assertEqual(w.notification_banner.title.full_text, 'On')
        self.assertTrue(w.notification_banner.message.isHidden())

    def test_bundled_font_is_selected_and_fallback_still_works(self):
        from branding import configure_fonts
        from ui_tokens import resolved_family, NUMERIC, font, stable_digits
        configure_fonts(test_hover.APP)
        self.assertIn(resolved_family(), ('Inter Variable', 'Inter'))
        for role in NUMERIC:
            self.assertTrue(stable_digits(font(role)))
        with patch('ui_tokens.QFontDatabase.families', return_value=['Segoe UI']):
            self.assertEqual(resolved_family(), 'Segoe UI')
