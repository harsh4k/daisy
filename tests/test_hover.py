import os
import json
import tempfile
import types
import unittest
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPoint, QRect, QObject, pyqtSignal, QBuffer, QIODevice, QCoreApplication, QEvent
from PyQt6.QtGui import QImage, QColor
import main
import settle

APP = QApplication.instance() or QApplication([])
import branding
# Register the real Windows UI fonts exactly as the application does.
branding.configure_fonts(APP)

def fake_monitors(window):
    monitor = types.SimpleNamespace(stop=lambda: None, city='Test', lat=0, lon=0,
                                    prev_track=lambda: None, next_track=lambda: None,
                                    toggle_play_pause=lambda: None)
    for name in ('perf', 'media', 'key', 'notif', 'weather'):
        setattr(window, name + '_monitor', monitor)

class InertMonitor(QObject):
    metrics_updated = pyqtSignal(dict)
    media_updated = pyqtSignal(str, str, str, str)
    artwork_updated = pyqtSignal(bytes)
    timeline_updated = pyqtSignal(float, float)
    source_updated = pyqtSignal(str)
    lyrics_updated = pyqtSignal(str)
    lock_changed = pyqtSignal(str, bool)
    notification_received = pyqtSignal(str, str, str)
    notification_recorded = pyqtSignal(object)
    access_changed = pyqtSignal(str)
    weather_updated = pyqtSignal(dict)
    location_updated = pyqtSignal(bool, str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.city, self.lat, self.lon = 'Test', 0, 0

    def start(self):
        pass

    def stop(self):
        pass

    def prev_track(self):
        pass

    next_track = prev_track
    toggle_play_pause = prev_track


class InitialMediaMonitor(InertMonitor):
    def start(self):
        image = QImage(8, 8, QImage.Format.Format_RGB32)
        image.fill(QColor('red'))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        self.media_updated.emit('Playing', 'First track', 'Artist', '')
        self.artwork_updated.emit(bytes(buffer.data()))
        self.source_updated.emit('Spotify')
        self.timeline_updated.emit(63, 240)


class HoverTests(unittest.TestCase):
    def window(self, config=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        if config is not None:
            with open(os.path.join(tmp.name, 'config.json'), 'w') as f:
                json.dump(config, f)
        with patch.object(main, '__file__', os.path.join(tmp.name, 'main.py')), \
             patch.object(main.DynamicIsland, 'setup_monitors', fake_monitors), \
             patch.object(main.DynamicIsland, 'setup_autostart'):
            window = main.DynamicIsland()
        # Desktop-focused tests must not inherit the user's active browser/game.
        # Dedicated policy tests replace these guards with their explicit inputs.
        window.game_guard = types.SimpleNamespace(is_active=lambda: False)
        window.browser_guard = types.SimpleNamespace(is_active=lambda: False, restore_focus=lambda: None)
        for name in ('power_timer', 'master_timer', 'anim_timer', 'hit_timer'):
            getattr(window, name).stop()
        window.show()
        def dispose_window():
            window.anim_group.stop()
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            APP.processEvents()
        self.addCleanup(dispose_window)
        return window

    def test_hover_dashboard_survives_rapid_reversal_without_text_drift(self):
        w = self.window()
        self.assertTrue(hasattr(w, 'dashboard'), 'Hover needs the two-card dashboard')
        for style in ('Default', 'Liquid Glass', 'Notch Nook'):
            w.island_style = style
            for state in ('Hover', 'Idle', 'Hover', 'Idle', 'Hover'):
                if APP.focusWidget():
                    APP.focusWidget().clearFocus()
                w.change_state(state)
                QTest.qWait(30)
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual((w.island_w, w.island_h), (624, 272))
            self.assertEqual(w.content_container.pos(), QPoint(0, 0))
            self.assertEqual(w.content_container.width(), 624)
            before = w.dashboard.pos()
            QTest.qWait(300)
            self.assertEqual(w.dashboard.pos(), before)
            self.assertFalse(w.dashboard.isHidden())
            if APP.focusWidget():
                APP.focusWidget().clearFocus()
            w.change_state('Idle')
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual((w.island_w, w.island_h), (180, 40))
            self.assertTrue(w.dashboard.isHidden())

    def test_stage_bar_sits_above_the_page_with_crumb_status_and_power(self):
        w = self.window()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        self.assertLess(w.navigation.y() + w.navigation.height(), w.feature_scroll.y() + 1)
        self.assertEqual(len(w.power_buttons), 1)
        self.assertFalse(w.power_buttons[0].icon().isNull())
        self.assertEqual(w.stage_bar.crumb.text(), 'Now')
        for button in w.nav_buttons + w.power_buttons:
            self.assertTrue(button.toolTip(), button.accessibleName())

    def test_dock_stays_inside_each_feature_shell(self):
        w = self.window()
        w.change_state('Hover')
        for feature in w.features:
            w.select_feature(feature)
            QTest.qWait(260)
            for button in w.nav_buttons + w.power_buttons:
                bounds = QRect(button.mapTo(w.content_container, QPoint()), button.size())
                self.assertTrue(w.content_container.rect().contains(bounds), (feature, button.accessibleName(), bounds))

    def test_restart_and_shutdown_require_confirmation(self):
        w = self.window()
        self.assertTrue(hasattr(w, 'request_action'), 'Power actions need guarded dispatch')
        with patch.object(main.subprocess, 'Popen') as dispatch, \
             patch.object(main.QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            w.request_action('shutdown')
            w.request_action('restart')
            dispatch.assert_not_called()
        with patch.object(main.subprocess, 'Popen') as dispatch, \
             patch.object(main.QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            w.request_action('restart')
            self.assertIn('/r', dispatch.call_args.args[0])

    def test_invalid_settings_normalize_and_theme_persists(self):
        for config in ([], {'tasks': None}, {'tasks': [{}]}, {'theme': 'unknown'}):
            w = self.window(config)
            self.assertTrue(hasattr(w, 'theme'), 'Theme must resolve before painting')
            self.assertIsInstance(w.settings['tasks'], list)
            self.assertEqual(w.theme['name'], 'Dark Matter')
            w.set_theme('Rose')
            with open(w.config_path) as f:
                self.assertEqual(json.load(f)['theme'], 'Rose')

    def test_notification_does_not_interrupt_task_editor(self):
        w = self.window()
        w.current_state = 'Hover'
        w.is_editing_tasks = True
        w.show_notification('App', 'Title', 'Body')
        self.assertEqual(w.current_state, 'Hover')
        self.assertFalse(w.revert_timer.isActive())

    def test_editor_saves_original_compatibility_preference(self):
        w = self.window()
        w.current_state = 'Hover'
        w.current_feature_index = w.features.index('calendar')
        w.open_task_editor()
        self.assertTrue(w.compatibility_mode)
        w.save_and_close_editor()
        with open(w.config_path) as stream:
            self.assertFalse(json.load(stream)['compatibility_mode'])

    def test_failed_atomic_save_preserves_existing_preferences(self):
        w = self.window({'theme': 'Graphite'})
        with patch.object(main.os, 'replace', side_effect=OSError('read only')), \
             patch.object(main.QMessageBox, 'warning'):
            self.assertFalse(w.save_settings())
        with open(w.config_path) as stream:
            self.assertEqual(json.load(stream), {'theme': 'Graphite'})

    def test_deferred_notification_is_shown_after_editor_closes(self):
        w = self.window()
        w.current_state = 'Hover'
        w.current_feature_index = w.features.index('calendar')
        w.open_task_editor()
        w.show_notification('Calendar', 'Reminder', 'Call soon')
        w.save_and_close_editor()
        self.assertEqual(w.current_state, 'Notify')
        self.assertEqual(w.event_text, 'Reminder: Call soon')

    def test_settings_wrong_value_types_do_not_crash_startup(self):
        w = self.window({'theme': [], 'location': None, 'lat': 'oops', 'lon': None,
                         'tasks': [{'name': 'Task', 'time': 'Now', 'category': None, 'color': None}]})
        self.assertEqual(w.theme['name'], 'Dark Matter')
        self.assertIsInstance(w.settings['location'], str)
        self.assertIsInstance(w.settings['lat'], (int, float))

    def test_theme_switch_updates_legacy_month_and_editor_focus(self):
        w = self.window()
        w.set_theme('Rose')
        # Today's ring in the month is drawn in the new accent.
        self.assertEqual(w.calendar_page.grid.theme['accent'], w.theme['accent'])
        self.assertIn(w.theme['accent'], w.calendar_page.styleSheet())
        self.assertFalse(w.edit_name.styleSheet())

    def test_initial_media_signals_reach_dashboard(self):
        w = self.window()
        with patch.object(main, 'PerfMonitor', InertMonitor), \
             patch.object(main, 'MediaMonitor', InitialMediaMonitor), \
             patch.object(main, 'KeyLockMonitor', InertMonitor), \
             patch.object(main, 'NotificationMonitor', InertMonitor), \
             patch.object(main, 'WeatherMonitor', InertMonitor):
            w.setup_monitors()
        self.assertEqual(w.dashboard.source.text(), 'Spotify')
        self.assertEqual(w.dashboard.elapsed.text(), '1:03')
        self.assertFalse(w.dashboard.artwork.pixmap().isNull())
        w.media_monitor.source_updated.emit('SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify')
        self.assertEqual(w.dashboard.source.text(), 'Spotify')
        w.media_monitor.source_updated.emit('Chrome.exe')
        self.assertEqual(w.dashboard.source.text(), 'Browser')

    def test_source_launch_does_not_change_installed_autostart(self):
        w = self.window()
        with patch.object(main.sys, 'frozen', False, create=True), \
             patch.object(main, 'set_autostart') as register:
            w.setup_autostart()
            register.assert_not_called()
        with patch.object(main.sys, 'frozen', True, create=True), \
             patch.object(main, 'set_autostart') as register:
            w.settings['start_with_windows'] = False
            w.setup_autostart()
            register.assert_called_once_with(False)

    def test_keyboard_focus_keeps_hover_open_after_pointer_leaves(self):
        w = self.window()
        w.change_state('Hover')
        QTest.qWait(280)
        w.activateWindow()
        w.nav_buttons[0].setFocus()
        APP.processEvents()
        self.assertTrue(w.isActiveWindow())
        self.assertIs(APP.focusWidget(), w.nav_buttons[0])
        # A timer may already have been armed before keyboard focus arrived.
        w.revert_timer.start(1200)
        with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
            w.check_mouse_position()
            QTest.qWait(1300)
        self.assertEqual(w.current_state, 'Hover')
        self.assertFalse(w.revert_timer.isActive())
        # Losing activation must release even a stale focus reference.
        other = main.QWidget()
        self.addCleanup(other.close)
        other.show()
        other.activateWindow()
        APP.processEvents()
        self.assertFalse(w.isActiveWindow())
        with patch.object(main.QCursor, 'pos', return_value=QPoint(-1000, -1000)):
            w.check_mouse_position()
            QTest.qWait(1300)
        self.assertEqual(w.current_state, 'Idle')

    def test_dashboard_fits_small_screen_and_available_origin(self):
        w = self.window()
        screen = types.SimpleNamespace(availableGeometry=lambda: QRect(-500, 100, 500, 400))
        with patch.object(w, 'screen', return_value=screen):
            for style in ('Default', 'Liquid Glass', 'Notch Nook'):
                w.island_style = style
                w.recenter_window()
                w.change_state('Hover')
                w.execute_liquid_transition()
                QTest.qWait(280)
                self.assertEqual(w.pos(), QPoint(-500, 100))
                self.assertTrue(w.rect().contains(w.get_island_rect().toAlignedRect()))
                dashboard = w.dashboard
                self.assertLessEqual(dashboard.width(), 468)
                self.assertTrue(dashboard.rect().contains(dashboard.media_card.geometry()))
                self.assertTrue(dashboard.rect().contains(dashboard.glance_column.geometry()))
                for button in dashboard.findChildren(main.QPushButton):
                    bounds = QRect(button.mapTo(dashboard, QPoint(0, 0)), button.size())
                    self.assertTrue(dashboard.rect().contains(bounds), button.accessibleName())

if __name__ == '__main__':
    unittest.main()
