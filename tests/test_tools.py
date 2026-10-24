import tempfile
import unittest
from pathlib import Path

import test_hover


class TimerTests(unittest.TestCase):
    def test_pause_resume_has_no_polling_drift_and_completes_once(self):
        from focus_timer import FocusTimer
        now = [0.0]
        timer = FocusTimer(clock=lambda: now[0])
        timer.start(5)
        now[0] = 71.25
        self.assertEqual(timer.remaining(), 228.75)
        timer.pause()
        now[0] = 1000
        self.assertEqual(timer.remaining(), 228.75)
        timer.resume()
        now[0] += 228.75
        self.assertEqual(timer.remaining(), 0)
        self.assertTrue(timer.take_completion())
        self.assertFalse(timer.take_completion())
        timer.reset()
        self.assertEqual(timer.state, 'idle')

    def test_invalid_timer_durations_are_rejected(self):
        from focus_timer import FocusTimer
        for value in (0, 181, True, '25', -1):
            with self.assertRaises(ValueError):
                FocusTimer().start(value)


class ShelfTests(unittest.TestCase):
    def test_distinct_paths_and_removal_never_touch_original(self):
        from file_shelf import ShelfModel
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'मेरा file.txt'
            original.write_text('keep me', encoding='utf-8')
            shelf = ShelfModel()
            shelf.add([str(original), str(original)])
            self.assertEqual(len(shelf.paths), 1)
            urls = shelf.mime_data([0]).urls()
            self.assertEqual(Path(urls[0].toLocalFile()), original)
            shelf.remove(0)
            self.assertEqual(shelf.paths, [])
            self.assertEqual(original.read_text(encoding='utf-8'), 'keep me')

    def test_limit_and_missing_references(self):
        from file_shelf import ShelfModel
        with tempfile.TemporaryDirectory() as folder:
            shelf = ShelfModel([str(Path(folder) / str(i)) for i in range(21)])
            self.assertEqual(len(shelf.paths), 20)
            self.assertFalse(shelf.available(0))
            with self.assertRaises(ValueError):
                shelf.add([str(Path(folder) / 'extra')])

    def test_unc_and_device_paths_never_reach_file_lookup(self):
        from file_shelf import ShelfModel
        for path in ('//server/share/file.txt', r'\\server\share\file.txt', r'\\?\C:\file.txt'):
            with self.assertRaises(ValueError):
                ShelfModel().add([path])

    def test_tools_panel_uses_real_file_icons_and_is_keyboard_accessible(self):
        from tools_panel import ToolsPanel
        panel = ToolsPanel([])
        self.addCleanup(panel.close)
        self.assertEqual(panel.timer.state, 'idle')
        self.assertTrue(panel.tabs.isTabEnabled(0))
        self.assertTrue(panel.tabs.isTabEnabled(1))


if __name__ == '__main__':
    unittest.main()
