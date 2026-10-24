import unittest
from types import SimpleNamespace
from unittest.mock import patch


class EntryTests(unittest.TestCase):
    def test_restart_launches_only_after_lock_release(self):
        import desktop_entry
        events = []
        app = SimpleNamespace(setQuitOnLastWindowClosed=lambda _: None, exec=lambda: 0)
        window = SimpleNamespace(show=lambda: None, restart_requested=True,
            open_settings=lambda: None, request_restart=lambda: None, open_logs=lambda: None,
            close=lambda: None)
        tray = SimpleNamespace(tray=SimpleNamespace(hide=lambda: None))
        lock = SimpleNamespace(unlock=lambda: events.append('unlock'))
        with patch.object(desktop_entry.QApplication, 'instance', return_value=app), \
             patch.object(desktop_entry, 'configure_application'), \
             patch.object(desktop_entry, 'configure_diagnostics'), \
             patch.object(desktop_entry, 'shutdown_diagnostics'), \
             patch.object(desktop_entry, 'acquire_instance_lock', return_value=lock), \
             patch.object(desktop_entry, 'RuntimeTray', return_value=tray), \
             patch.object(desktop_entry, 'launch_restart', side_effect=lambda: events.append('launch') or True):
            self.assertEqual(desktop_entry.run(lambda: window), 0)
        self.assertEqual(events, ['unlock', 'launch'])

    def test_failed_show_cleans_up_before_unlock(self):
        import desktop_entry
        events = []
        app = SimpleNamespace(setQuitOnLastWindowClosed=lambda _: None, exec=lambda: 0)
        def fail():
            raise RuntimeError('show failed')
        window = SimpleNamespace(show=fail, restart_requested=False,
            open_settings=lambda: None, request_restart=lambda: None, open_logs=lambda: None,
            close=lambda: events.append('close'))
        tray = SimpleNamespace(tray=SimpleNamespace(hide=lambda: None))
        lock = SimpleNamespace(unlock=lambda: events.append('unlock'))
        with patch.object(desktop_entry.QApplication, 'instance', return_value=app), \
             patch.object(desktop_entry, 'configure_application'), \
             patch.object(desktop_entry, 'configure_diagnostics'), \
             patch.object(desktop_entry, 'shutdown_diagnostics'), \
             patch.object(desktop_entry, 'acquire_instance_lock', return_value=lock), \
             patch.object(desktop_entry, 'RuntimeTray', return_value=tray), \
             patch.object(desktop_entry.QMessageBox, 'critical'):
            self.assertEqual(desktop_entry.run(lambda: window), 1)
        self.assertEqual(events, ['close', 'unlock'])
