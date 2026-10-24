import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_daisy_brand_and_icon(self):
        import branding
        self.assertEqual(branding.APP_NAME, 'Daisy')
        self.assertFalse(branding.app_icon().isNull())

    def test_frozen_startup_command_quotes_executable(self):
        from app_runtime import startup_command
        with patch('sys.frozen', True, create=True), patch('sys.executable', r'X:\My Apps\Daisy.exe'):
            self.assertEqual(startup_command(), '"X:\\My Apps\\Daisy.exe"')

    def test_source_startup_command_targets_main_not_test_runner(self):
        from app_runtime import startup_command
        with patch('sys.frozen', False, create=True):
            command = startup_command()
        self.assertIn('main.py"', command)
        self.assertNotIn('unittest', command)
        self.assertTrue(command.startswith('"'))

    def test_only_one_instance_holds_lock(self):
        from app_runtime import acquire_instance_lock
        with tempfile.TemporaryDirectory() as directory:
            lock = acquire_instance_lock(directory)
            self.assertIsNotNone(lock)
            self.assertIsNone(acquire_instance_lock(directory))
            lock.unlock()
            replacement = acquire_instance_lock(directory)
            self.assertIsNotNone(replacement)
            replacement.unlock()

    def test_disabled_startup_does_not_register_again(self):
        from app_runtime import set_autostart
        with patch('app_runtime.winreg') as registry:
            registry.QueryValueEx.side_effect = FileNotFoundError()
            self.assertTrue(set_autostart(False))
            registry.SetValueEx.assert_not_called()
            self.assertTrue(any(call.args[1] == 'Daisy' for call in registry.DeleteValue.call_args_list))

    def test_startup_migrates_legacy_entry(self):
        from app_runtime import set_autostart
        with patch('app_runtime.winreg') as registry:
            registry.QueryValueEx.return_value = ('"X:\\Apps\\DynamicIsland\\dist\\DynamicIsland.exe"', 1)
            self.assertTrue(set_autostart(True))
            self.assertEqual(registry.SetValueEx.call_args.args[1], 'Daisy')
            registry.DeleteValue.assert_called_with(registry.CreateKeyEx.return_value.__enter__.return_value, 'DynamicIsland')

if __name__ == '__main__':
    unittest.main()
