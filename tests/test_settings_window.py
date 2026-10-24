"""Settings preview and cancellation cannot mutate operational preferences."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PyQt6.QtWidgets import QApplication, QDialogButtonBox
from settings_window import SettingsDialog
from settings_draft import validate_draft

APP = QApplication.instance() or QApplication([])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.original = {'theme': 'Dark Matter', 'city': 'Mumbai, India',
                         'tasks': [{'text': 'keep'}], 'lat': 19.076, 'lon': 72.8777}
        self.saved = []
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.close()
            dialog.deleteLater()
        APP.processEvents()

    def dialog(self, callback=None, **kwargs):
        def save(draft):
            self.saved.append(copy.deepcopy(draft))
            return True, ''
        widget = SettingsDialog(self.original, callback or save, **kwargs)
        self.dialogs.append(widget)
        return widget

    def test_preview_cancel_never_changes_original_or_saves(self):
        before = copy.deepcopy(self.original)
        dialog = self.dialog()
        dialog.controls['theme'].setCurrentText('Amethyst')
        dialog.controls['island_style'].setCurrentText('Notch Nook')
        self.assertEqual(dialog.preview.settings['theme'], 'Amethyst')
        self.assertEqual(dialog.preview.settings['island_style'], 'Notch Nook')
        dialog.reject()
        self.assertEqual(self.original, before)
        self.assertEqual(self.saved, [])

    def test_apply_commits_once_preserves_unrelated_keys_and_ok_closes(self):
        dialog = self.dialog()
        dialog.controls['timer_default_minutes'].setValue(50)
        self.assertTrue(dialog.apply_changes())
        self.assertEqual(len(self.saved), 1)
        self.assertEqual(self.saved[0]['city'], 'Mumbai, India')
        self.assertEqual(self.saved[0]['tasks'], [{'text': 'keep'}])
        self.assertEqual(self.saved[0]['timer_default_minutes'], 50)
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_save_failure_keeps_draft_and_dialog_open(self):
        dialog = self.dialog(lambda _: (False, 'Cannot save preferences'))
        dialog.show()
        dialog.controls['theme'].setCurrentText('Rose')
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        self.assertTrue(dialog.isVisible())
        self.assertIn('Cannot save', dialog.error_label.text())
        self.assertEqual(dialog.draft['theme'], 'Rose')

    def test_invalid_gif_and_bad_rules_are_not_committed(self):
        dialog = self.dialog()
        dialog.controls['idle_icon'].setCurrentText('Custom GIF')
        dialog.controls['custom_idle_icon'].setText('missing.gif')
        self.assertFalse(dialog.apply_changes())
        self.assertEqual(self.saved, [])
        dialog.controls['idle_icon'].setCurrentText('Clock')
        dialog.draft['app_rules'] = {'not/exe.exe': 'hidden'}
        self.assertFalse(dialog.apply_changes())

    def test_malformed_settings_migrate_in_draft_only(self):
        self.original.update(theme=[], app_rules=[], autohide_delay=-1,
                             timer_default_minutes=False, preferred_media_source=3)
        dialog = self.dialog()
        self.assertEqual(dialog.draft['theme'], 'Dark Matter')
        self.assertEqual(dialog.draft['app_rules'], {})
        self.assertEqual(dialog.draft['timer_default_minutes'], 25)
        self.assertEqual(self.original['theme'], [])

    def test_actions_are_explicit_and_preferred_source_kept_when_absent(self):
        called = []
        self.original['preferred_media_source'] = 'spotify-id'
        dialog = self.dialog(actions={'logs': lambda: called.append('logs')},
                             media_sources=[{'id': 'browser', 'name': 'Browser'}])
        self.assertEqual(dialog.controls['preferred_media_source'].currentData(), 'spotify-id')
        dialog.action_buttons['logs'].click()
        self.assertEqual(called, ['logs'])
        self.assertEqual(self.saved, [])

    def test_external_draft_validation_rejects_invalid_scalar_types(self):
        dialog = self.dialog()
        for key, value in (('autohide_delay', True), ('autohide_delay', 8),
                           ('compatibility_mode', 'yes'), ('start_with_windows', 1),
                           ('preferred_media_source', []), ('custom_idle_icon', None),
                           ('theme', []), ('timer_default_minutes', 181)):
            draft = copy.deepcopy(dialog.draft)
            draft[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_draft(draft)

    def test_rule_editor_rejects_duplicate_override_and_restores_defaults(self):
        dialog = self.dialog()
        page = dialog.rules_page
        self.assertTrue(page.set_rule('Chrome.EXE', 'hover'))
        self.assertEqual(dialog.draft['app_rules'], {'chrome.exe': 'hover'})
        self.assertFalse(page.set_rule('chrome.exe', 'hidden'))
        self.assertEqual(dialog.draft['app_rules'], {'chrome.exe': 'hover'})
        page.restore_defaults()
        self.assertEqual(dialog.draft['app_rules'], {})
        self.assertEqual(self.saved, [])
