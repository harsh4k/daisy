import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import test_hover
import settle
from PyQt6.QtTest import QTest


class UpgradeIntegrationTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_new_settings_defaults_and_tools_navigation(self):
        w = self.window({'location': 'Mumbai, India', 'app_rules': []})
        self.assertEqual(w.settings['app_rules'], {})
        self.assertEqual(w.settings['timer_default_minutes'], 25)
        self.assertIn('tools', w.features)
        w.select_feature('tools')
        self.assertTrue(settle.settle_shell(w))
        self.assertTrue(w.tools_panel.isVisible())

    def test_apply_updates_once_and_preserves_unrelated_preferences(self):
        w = self.window({'location': 'Mumbai, India', 'custom_data': {'keep': 7}})
        draft = copy.deepcopy(w.settings)
        draft.update(theme='Amethyst', app_rules={'EXAMPLE.EXE': 'hidden'}, timer_default_minutes=15)
        ok, error = w.apply_preferences(draft)
        self.assertTrue(ok, error)
        saved = json.loads(Path(w.config_path).read_text())
        self.assertEqual(saved['custom_data'], {'keep': 7})
        self.assertEqual(saved['app_rules'], {'example.exe': 'hidden'})
        self.assertEqual(w.theme['name'], 'Amethyst')
        self.assertEqual(w.tools_panel.minutes.value(), 15)

    def test_failed_config_write_compensates_startup_and_keeps_live_state(self):
        w = self.window({'theme': 'Graphite', 'start_with_windows': True})
        before = Path(w.config_path).read_bytes()
        draft = copy.deepcopy(w.settings)
        draft.update(theme='Rose', start_with_windows=False)
        with patch('settings_controller.capture_startup_entries', return_value={'old': 'state'}), \
             patch('settings_controller.set_autostart', return_value=True), \
             patch('settings_controller.restore_startup_entries', return_value=True) as restore, \
             patch('settings_controller.write_preferences', side_effect=OSError('disk unavailable')):
            ok, error = w.apply_preferences(draft)
        self.assertFalse(ok)
        self.assertIn('save', error.lower())
        restore.assert_called_once_with({'old': 'state'})
        self.assertEqual(Path(w.config_path).read_bytes(), before)
        self.assertEqual(w.theme['name'], 'Graphite')

    def test_hidden_timer_completion_does_not_open_overlay(self):
        w = self.window()
        w.change_state('Hidden')
        w.on_timer_completed()
        self.assertEqual(w.current_state, 'Hidden')
        self.assertTrue(w.tools_panel.completion_pending)

    def test_shelf_persists_only_references(self):
        w = self.window()
        path = Path(w.config_path).with_name('original.txt')
        path.write_text('original')
        w.tools_panel.shelf.add_paths([str(path)])
        self.assertEqual(json.loads(Path(w.config_path).read_text())['shelf_paths'], [str(path)])
        w.tools_panel.shelf.list.setCurrentRow(0)
        w.tools_panel.shelf.remove_selected()
        self.assertEqual(path.read_text(), 'original')

    def test_settings_apply_keeps_live_task_and_location_changes(self):
        w = self.window({'tasks': [], 'location': 'Old city'})
        draft = copy.deepcopy(w.settings)
        w.settings.update(tasks=[{'name': 'New task', 'time': 'Now'}], location='Mumbai, India')
        draft['theme'] = 'Rose'
        ok, error = w.apply_preferences(draft)
        self.assertTrue(ok, error)
        self.assertEqual(w.settings['location'], 'Mumbai, India')
        self.assertEqual(w.settings['tasks'][0]['name'], 'New task')

    def test_apply_autohide_off_restores_clock_outside_click_mode(self):
        w = self.window()
        w.change_state('Hidden')
        draft = copy.deepcopy(w.settings)
        draft['autohide_delay'] = 0
        self.assertTrue(w.apply_preferences(draft)[0])
        self.assertEqual(w.current_state, 'Idle')


if __name__ == '__main__':
    unittest.main()
