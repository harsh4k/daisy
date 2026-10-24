import json
import logging
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
import app_runtime


class RuntimeToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_runtime_tools_contract_exists(self):
        for name in ('get_startup_status', 'capture_startup_entries',
                     'restore_startup_entries', 'restart_command', 'launch_restart'):
            self.assertTrue(callable(getattr(app_runtime, name, None)), name)

    def test_lock_contention_is_the_only_silent_duplicate(self):
        from PyQt6.QtCore import QLockFile
        with tempfile.TemporaryDirectory() as directory, patch('app_runtime.QLockFile') as lock_type:
            lock_type.LockError = QLockFile.LockError
            instance = lock_type.return_value
            instance.tryLock.return_value = False
            instance.error.return_value = QLockFile.LockError.LockFailedError
            self.assertIsNone(app_runtime.acquire_instance_lock(directory))
            for error in (QLockFile.LockError.PermissionError, QLockFile.LockError.UnknownError):
                instance.error.return_value = error
                with self.assertRaises(OSError):
                    app_runtime.acquire_instance_lock(directory)

    def test_startup_windows_disabled_is_authoritative(self):
        with patch('app_runtime.winreg') as registry:
            registry.QueryValueEx.side_effect = [('"Daisy.exe"', 1), (b'\x03' + bytes(11), 3)]
            self.assertEqual(app_runtime.get_startup_status()['state'], 'Disabled in Windows')
            registry.SetValueEx.assert_not_called()

    def test_startup_on_off_unavailable(self):
        with patch('app_runtime.winreg') as registry:
            registry.QueryValueEx.side_effect = [('"Daisy.exe"', 1), FileNotFoundError()]
            self.assertEqual(app_runtime.get_startup_status()['state'], 'Enabled')
            registry.QueryValueEx.side_effect = FileNotFoundError()
            self.assertEqual(app_runtime.get_startup_status()['state'], 'Off')
            registry.OpenKey.side_effect = PermissionError()
            self.assertEqual(app_runtime.get_startup_status()['state'], 'Unavailable')

    def test_registry_compensation_restores_exact_values_and_absence(self):
        with patch('app_runtime.winreg') as registry:
            registry.QueryValueEx.side_effect = [('old quoted command', 1), FileNotFoundError()]
            snapshot = app_runtime.capture_startup_entries()
            self.assertTrue(app_runtime.restore_startup_entries(snapshot))
            registry.SetValueEx.assert_called_once()
            self.assertEqual(registry.SetValueEx.call_args.args[1:], ('Daisy', 0, 1, 'old quoted command'))
            self.assertEqual(registry.DeleteValue.call_args.args[1], 'DynamicIsland')
            registry.CreateKeyEx.side_effect = PermissionError()
            with self.assertLogs('app_runtime', level='ERROR'):
                self.assertFalse(app_runtime.restore_startup_entries(snapshot))

    def test_restart_source_and_frozen_are_argument_lists(self):
        with patch('app_runtime.sys.frozen', True, create=True):
            self.assertEqual(app_runtime.restart_command(), [sys.executable])
        with patch('app_runtime.sys.frozen', False, create=True):
            args = app_runtime.restart_command()
            self.assertEqual(Path(args[-1]).name, 'main.py')
            self.assertNotIn('unittest', args)

    def test_restart_launch_is_once_without_shell_and_uses_app_directory(self):
        with patch('app_runtime.sys.frozen', True, create=True), \
                patch('app_runtime.sys.executable', r'X:\My Apps\Daisy.exe'), \
                patch('app_runtime.subprocess.Popen') as start:
            self.assertTrue(app_runtime.launch_restart())
            start.assert_called_once()
            self.assertEqual(start.call_args.args[0], [r'X:\My Apps\Daisy.exe'])
            self.assertEqual(start.call_args.kwargs['cwd'], r'X:\My Apps')
            self.assertFalse(start.call_args.kwargs.get('shell', False))
            start.side_effect = OSError('private content')
            with self.assertLogs('app_runtime', level='ERROR'):
                self.assertFalse(app_runtime.launch_restart())

    def test_source_restart_cwd_is_repo_not_callers_cwd(self):
        with patch('app_runtime.sys.frozen', False, create=True), \
                patch('app_runtime.subprocess.Popen') as start:
            self.assertTrue(app_runtime.launch_restart())
            self.assertEqual(start.call_args.kwargs['cwd'], str(Path(app_runtime.__file__).parent))

    def test_startup_malformed_approval_is_not_falsely_enabled(self):
        with patch('app_runtime.winreg') as registry:
            registry.QueryValueEx.side_effect = [('"Daisy.exe"', 1), (b'', 3)]
            self.assertEqual(app_runtime.get_startup_status()['state'], 'Unavailable')

    def test_capture_read_error_prevents_unsafe_compensation(self):
        with patch('app_runtime.winreg') as registry:
            registry.OpenKey.side_effect = PermissionError()
            with self.assertRaises(PermissionError):
                app_runtime.capture_startup_entries()
            self.assertFalse(app_runtime.restore_startup_entries({}))
            registry.SetValueEx.assert_not_called()

    def test_private_exception_text_is_not_logged_and_rotation_is_bounded(self):
        import runtime_diagnostics as diagnostics
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(diagnostics.QStandardPaths, 'writableLocation', return_value=directory), \
                patch.object(diagnostics, 'LOG_BYTES', 1024):
            logs = diagnostics.configure_diagnostics()
            try:
                for index in range(100):
                    try:
                        raise ValueError('SECRET track task lyric settings content')
                    except ValueError:
                        logging.getLogger('daisy.test').exception('Private title %s', index)
                paths = list(logs.glob('daisy.log*'))
                self.assertLessEqual(len(paths), 3)
                self.assertGreaterEqual(len(paths), 2)
                for path in paths:
                    text = path.read_text(encoding='utf-8')
                    self.assertNotIn('SECRET', text)
                    self.assertNotIn('Private title', text)
                    self.assertLessEqual(path.stat().st_size, 1024)
                    record = json.loads(text.splitlines()[-1])
                    self.assertEqual(record['exception'], 'ValueError')
                    self.assertIn('session', record)
                self.assertEqual(diagnostics.diagnostic_info()['log_directory'], str(logs))
            finally:
                diagnostics.shutdown_diagnostics()

    def test_diagnostics_hooks_are_idempotent_private_and_restored(self):
        import runtime_diagnostics as diagnostics
        import threading
        from PyQt6.QtCore import QtMsgType
        from types import SimpleNamespace
        old_python, old_thread = sys.excepthook, threading.excepthook
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(diagnostics.QStandardPaths, 'writableLocation', return_value=directory):
            logs = diagnostics.configure_diagnostics()
            try:
                self.assertEqual(logs, diagnostics.configure_diagnostics())
                self.assertEqual(sum(isinstance(h, diagnostics.RotatingFileHandler)
                                     for h in logging.getLogger().handlers), 1)
                try:
                    raise RuntimeError('PRIVATE TOKEN')
                except RuntimeError:
                    kind, value, tb = sys.exc_info()
                    sys.excepthook(kind, value, tb)
                    threading.excepthook(SimpleNamespace(exc_type=kind, exc_value=value, exc_traceback=tb))
                diagnostics._qt_message(QtMsgType.QtWarningMsg, None, 'PRIVATE Qt URL')
                text = (logs / 'daisy.log').read_text(encoding='utf-8')
                self.assertNotIn('PRIVATE', text)
                for event in ('uncaught_python', 'uncaught_thread', 'qt_warning'):
                    self.assertIn(event, text)
            finally:
                diagnostics.shutdown_diagnostics()
            self.assertIs(sys.excepthook, old_python)
            self.assertIs(threading.excepthook, old_thread)

    def test_tray_keeps_restart_daisy_separate_and_invokes_callbacks(self):
        from runtime_tray import RuntimeTray
        calls = []
        tray = RuntimeTray(None, lambda: calls.append('settings'), lambda: calls.append('restart'),
                           lambda: calls.append('logs'), lambda: calls.append('quit'))
        try:
            labels = [a.text() for a in tray.menu.actions()]
            self.assertIn('Restart Daisy', labels)
            self.assertNotIn('Restart PC', labels)
            for action in tray.menu.actions():
                if action.text() == 'Restart Daisy':
                    action.trigger()
            self.assertEqual(calls, ['restart'])
        finally:
            tray.tray.hide()

    def test_fatal_sink_preserves_previous_until_new_bytes_and_caps_output(self):
        import io
        import runtime_fatal
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'crash.log'
            path.write_bytes(b'previous crash')
            self.assertEqual(runtime_fatal.copy_bounded(io.BytesIO(), path, 1024), 0)
            self.assertEqual(path.read_bytes(), b'previous crash')
            stream = io.BytesIO(b'x' * 4096)
            self.assertEqual(runtime_fatal.copy_bounded(stream, path, 1024), 0)
            self.assertEqual(path.read_bytes(), b'x' * 1024)
            self.assertEqual(stream.read(), b'')

    def test_fatal_capture_uses_pipe_even_without_native_stderr(self):
        import runtime_diagnostics as diagnostics
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(diagnostics.QStandardPaths, 'writableLocation', return_value=directory), \
                patch('runtime_diagnostics.sys.__stderr__', None), \
                patch('runtime_diagnostics.faulthandler.enable') as enable, \
                patch('runtime_diagnostics.faulthandler.disable'), \
                patch('runtime_fatal.subprocess.Popen') as start:
            diagnostics.configure_diagnostics()
            try:
                self.assertTrue(diagnostics.enable_fatal_capture())
                enable.assert_called_once_with(file=start.return_value.stdin, all_threads=True)
                args = start.call_args.args[0]
                self.assertIn('--daisy-fatal-sink', args)
                self.assertEqual(Path(args[-1]).name, 'crash.log')
                self.assertEqual(start.call_args.kwargs['stdin'], -1)
            finally:
                diagnostics.shutdown_diagnostics()
            start.return_value.stdin.close.assert_called_once()
            start.return_value.wait.assert_called_once()

    def test_frozen_sink_command_never_starts_main_or_source_script(self):
        import runtime_fatal
        with patch('runtime_fatal.sys.frozen', True, create=True), \
                patch('runtime_fatal.sys.executable', r'X:\Apps\Daisy.exe'):
            args = runtime_fatal.sink_command(Path('crash.log'))
            self.assertEqual(args[:2], [r'X:\Apps\Daisy.exe', '--daisy-fatal-sink'])


if __name__ == '__main__':
    unittest.main()
