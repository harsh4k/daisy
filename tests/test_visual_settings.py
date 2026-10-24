"""Visual preferences remain detached, validated, and quiet until enabled."""
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PyQt6.QtCore import QRect
from PIL import Image
from PyQt6.QtGui import QMovie
from PyQt6.QtWidgets import QApplication
from settings_draft import create_draft, validate_draft
from settings_window import SettingsDialog

APP = QApplication.instance() or QApplication([])


class VisualSettingsTests(unittest.TestCase):
    def test_resizing_settings_adapts_preview_and_navigation(self):
        dialog = SettingsDialog({}, lambda _: (True, ''))
        try:
            dialog.resize(680, 540)
            dialog.show()
            APP.processEvents()
            self.assertTrue(dialog._compact_layout)
            self.assertLessEqual(dialog.preview.height(), 100)
            self.assertEqual(dialog.navigation.verticalScrollBar().maximum(), 0)
            dialog.resize(900, min(760, dialog.maximumHeight()))
            APP.processEvents()
            if dialog.height() >= 620:
                self.assertFalse(dialog._compact_layout)
                self.assertEqual(dialog.preview.height(), 150)
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_defaults_preserve_existing_choices_and_reject_bad_visual_types(self):
        original = dict(theme='Amethyst', animation_style='Fluid Blobs', idle_icon='Daisy')
        draft = create_draft(original)
        self.assertEqual(draft['surface_treatment'], 'neutral')
        self.assertEqual(draft['motion_mode'], 'auto')
        self.assertFalse(draft['decorative_effects_enabled'])
        for key, value in original.items():
            self.assertEqual(draft[key], value)
        for key, bad in [('surface_treatment', 'blue'), ('motion_mode', []),
                         ('decorative_effects_enabled', 1)]:
            invalid = dict(draft, **{key: bad})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_draft(invalid)
            self.assertEqual(create_draft(invalid)[key], draft[key])

    def test_visual_controls_preview_cancel_and_apply(self):
        original = create_draft({'city': 'Mumbai, India', 'idle_icon': 'Orbit'})
        before = copy.deepcopy(original)
        saved = []
        dialog = SettingsDialog(original, lambda draft: (saved.append(draft) is None, ''))
        try:
            dialog.controls['surface_treatment'].setCurrentIndex(1)
            dialog.controls['motion_mode'].setCurrentIndex(2)
            dialog.controls['decorative_effects_enabled'].setChecked(True)
            self.assertEqual(dialog.preview.settings['surface_treatment'], 'tinted')
            self.assertEqual(dialog.preview.settings['motion_mode'], 'reduced')
            self.assertEqual(original, before)
            self.assertEqual(saved, [])
            self.assertTrue(dialog.apply_changes())
            self.assertEqual(saved[0]['surface_treatment'], 'tinted')
            self.assertEqual(saved[0]['idle_icon'], 'Orbit')
            self.assertEqual(saved[0]['city'], 'Mumbai, India')
        finally:
            dialog.reject()
            dialog.deleteLater()

    def test_preview_reduced_motion_stops_background_and_idle_loops(self):
        dialog = SettingsDialog({'idle_icon': 'Orbit'}, lambda _: (True, ''))
        try:
            dialog.show()
            dialog.controls['motion_mode'].setCurrentIndex(1)
            APP.processEvents()
            self.assertTrue(dialog.preview.icon.loop_timer.isActive())
            self.assertFalse(dialog.preview._timer.isActive())
            dialog.preview.set_view('Expanded')
            APP.processEvents()
            self.assertFalse(dialog.preview._timer.isActive())
            dialog.controls['decorative_effects_enabled'].setChecked(True)
            dialog.controls['motion_mode'].setCurrentIndex(1)
            self.assertTrue(dialog.preview._timer.isActive())
            dialog.controls['motion_mode'].setCurrentIndex(2)
            self.assertFalse(dialog.preview._timer.isActive())
            dialog.preview.set_view('Compact')
            APP.processEvents()
            self.assertFalse(dialog.preview.icon.loop_timer.isActive())
            self.assertEqual(dialog.preview.icon.style_name, 'Orbit')
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_constrained_appearance_scrolls_without_horizontal_clipping(self):
        dialog = SettingsDialog({}, lambda _: (True, ''))
        try:
            dialog.resize(680, 540)
            dialog.show()
            APP.processEvents()
            scroll = dialog.stack.widget(0)
            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_custom_gif_reduced_preview_stays_static_without_replacing_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'idle.gif'
            Image.new('RGB', (12, 12), 'purple').save(path, save_all=True,
                append_images=[Image.new('RGB', (12, 12), 'grey')], duration=50, loop=0)
            settings = dict(idle_icon='Custom GIF', custom_idle_icon=str(path),
                            motion_mode='reduced', decorative_effects_enabled=True)
            dialog = SettingsDialog(settings, lambda _: (True, ''))
            try:
                dialog.show()
                APP.processEvents()
                movie = dialog.preview.icon._movie
                self.assertIsNotNone(movie)
                self.assertNotEqual(movie.state(), QMovie.MovieState.Running)
                self.assertEqual(dialog.draft['custom_idle_icon'], str(path))
                self.assertEqual(dialog.preview.icon.style_name, 'Custom GIF')
                self.assertFalse(dialog.preview.icon.pixmap().isNull())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_cancel_visual_edits_never_calls_persistence(self):
        original = {'theme': 'Rose', 'idle_icon': 'Daisy'}
        saved = []
        dialog = SettingsDialog(original, lambda draft: (saved.append(draft) is None, ''))
        dialog.controls['surface_treatment'].setCurrentIndex(1)
        dialog.controls['decorative_effects_enabled'].setChecked(True)
        dialog.reject()
        self.assertEqual(original, {'theme': 'Rose', 'idle_icon': 'Daisy'})
        self.assertEqual(saved, [])
        dialog.deleteLater()

    def test_short_high_dpi_screen_keeps_footer_inside_available_geometry(self):
        screen = SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 960, 510))
        with patch('PyQt6.QtWidgets.QApplication.primaryScreen', return_value=screen):
            dialog = SettingsDialog({}, lambda _: (True, ''))
        try:
            dialog.resize(680, 540)
            dialog.show()
            APP.processEvents()
            self.assertLessEqual(dialog.minimumHeight(), 470)
            self.assertLessEqual(dialog.height(), 470)
            self.assertLessEqual(dialog.buttons.geometry().bottom(), dialog.height() - 8)
            scroll = dialog.stack.widget(0)
            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_motion_preference_updates_settings_hover_feedback(self):
        dialog = SettingsDialog({'motion_mode': 'full'}, lambda _: (True, ''))
        try:
            button = dialog.action_buttons['restart']
            self.assertFalse(button._daisy_hover.reduced)
            dialog.controls['motion_mode'].setCurrentIndex(2)
            self.assertTrue(button._daisy_hover.reduced)
        finally:
            dialog.close()
            dialog.deleteLater()

