import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import importlib.util
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import QEvent, QCoreApplication
from PyQt6.QtTest import QTest
import settle
APP = QApplication.instance() or QApplication([])

class HoverFeedbackTests(unittest.TestCase):
    def test_feedback_settles_without_moving_control_and_reduced_is_immediate(self):
        self.assertIsNotNone(importlib.util.find_spec('hover_feedback'))
        from hover_feedback import install_hover_feedback
        button = QPushButton('Play')
        button.resize(80,40)
        button.show()
        self.addCleanup(button.close)
        install_hover_feedback(button, '#29292d', False)
        bounds = button.geometry()
        QCoreApplication.sendEvent(button,QEvent(QEvent.Type.Enter))
        self.assertTrue(settle.wait_for_animation(button._daisy_hover.animation))
        self.assertEqual(button.geometry(),bounds)
        self.assertEqual(button._daisy_hover.progress,1.)
        install_hover_feedback(button, '#29292d', True)
        QCoreApplication.sendEvent(button,QEvent(QEvent.Type.Leave))
        self.assertEqual(button._daisy_hover.progress,0.)
        self.assertFalse(button._daisy_hover.animation.state().value)
