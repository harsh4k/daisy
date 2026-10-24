import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMovie, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

APP = QApplication.instance() or QApplication([])


class IdleIconTests(unittest.TestCase):
    def setUp(self):
        from idle_icon import IdleIcon
        self.icon = IdleIcon()
        self.icon.show()
        APP.processEvents()

    def tearDown(self):
        self.icon.close()
        self.icon.deleteLater()
        APP.processEvents()

    def gif_path(self, directory):
        path = Path(directory) / 'loop.gif'
        frames = [Image.new('RGBA', (16, 16), color) for color in ('red', 'blue')]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=150, loop=0)
        return str(path)

    def test_clock_is_static_and_centered(self):
        self.assertEqual(self.icon.size().width(), 22)
        self.assertEqual(self.icon.alignment(), Qt.AlignmentFlag.AlignCenter)
        first = self.icon.pixmap().toImage()
        QTest.qWait(120)
        self.assertFalse(self.icon._timer.isActive())
        self.assertEqual(first, self.icon.pixmap().toImage())

    def test_each_builtin_loop_renders_and_moves(self):
        for style in ('Orbit', 'Pulse', 'Wave', 'Daisy'):
            with self.subTest(style=style):
                self.assertTrue(self.icon.set_style(style))
                first = self.icon.pixmap().toImage()
                self.assertFalse(first.isNull())
                QTest.qWait(180)
                self.assertNotEqual(first, self.icon.pixmap().toImage())

    def test_hidden_and_inactive_pause_and_do_not_replace_notification(self):
        self.icon.set_style('Orbit')
        self.assertTrue(self.icon._timer.isActive())
        self.icon.hide()
        self.assertFalse(self.icon._timer.isActive())
        phase = self.icon._phase
        QTest.qWait(80)
        self.assertEqual(phase, self.icon._phase)
        self.icon.show()
        self.assertTrue(self.icon._timer.isActive())
        self.icon.set_active(False)
        marker = QPixmap(20, 20)
        marker.fill(Qt.GlobalColor.red)
        self.icon.setPixmap(marker)
        self.icon.set_color('purple')
        QTest.qWait(100)
        self.assertFalse(self.icon._timer.isActive())
        self.assertEqual(marker.toImage(), self.icon.pixmap().toImage())
        self.icon.set_active(True)
        self.assertTrue(self.icon._timer.isActive())

    def test_repeated_configuration_preserves_loop_and_gif(self):
        self.icon.set_style('Orbit')
        QTest.qWait(100)
        phase = self.icon._phase
        self.icon.set_style('Orbit')
        self.icon.set_color('white')
        self.assertEqual(phase, self.icon._phase)
        with tempfile.TemporaryDirectory() as directory:
            path = self.gif_path(directory)
            self.assertTrue(self.icon.set_style('Custom GIF', path))
            movie = self.icon._movie
            QTest.qWait(180)
            self.icon.set_style('Custom GIF', path)
            self.icon.set_color('purple')
            self.assertIs(movie, self.icon._movie)
            self.icon.hide()
            self.assertEqual(movie.state(), QMovie.MovieState.Paused)
            self.icon.show()
            self.assertEqual(movie.state(), QMovie.MovieState.Running)
            self.icon.set_active(False)
            self.assertEqual(movie.state(), QMovie.MovieState.Paused)
            self.icon.set_active(True)
            self.assertEqual(movie.state(), QMovie.MovieState.Running)

    def test_invalid_styles_and_files_fall_back_gracefully(self):
        for style, path in [('Unknown', ''), ('Custom GIF', ''),
                            ('Custom GIF', 'C:/does-not-exist.gif')]:
            self.assertFalse(self.icon.set_style(style, path))
            self.assertEqual(self.icon.style_name, 'Clock')
            self.assertFalse(self.icon.pixmap().isNull())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'broken.gif'
            path.write_text('invalid gif', encoding='utf-8')
            self.assertFalse(self.icon.set_style('Custom GIF', str(path)))
            self.assertEqual(self.icon.style_name, 'Clock')

    def test_custom_animation_loops_even_when_file_has_no_repeat_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'once.gif'
            frames = [Image.new('RGBA', (16, 16), color) for color in ('red', 'blue')]
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=70)
            self.assertTrue(self.icon.set_style('Custom GIF', str(path)))
            QTest.qWait(350)
            self.assertEqual(self.icon._movie.state(), QMovie.MovieState.Running)
            self.icon.set_active(False)
            QTest.qWait(150)
            self.assertEqual(self.icon._movie.state(), QMovie.MovieState.Paused)


if __name__ == '__main__':
    unittest.main()
