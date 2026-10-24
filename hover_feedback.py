"""Small paint-only hover feedback, with no layout or text movement."""
from PyQt6.QtCore import Qt, QEvent, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget, QPushButton, QToolButton
from ui_tokens import MOTION

class HoverFeedback(QWidget):
    def __init__(self, button):
        super().__init__(button)
        self.button = button
        self._progress = 0.
        self.reduced = False
        self.color = QColor()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet('background: transparent; border: none;')
        self.animation = QPropertyAnimation(self, b'progress', self)
        self.animation.setDuration(MOTION['hover'])
        button.installEventFilter(self)
        self.setGeometry(button.rect())
        self.show()

    @pyqtProperty(float)
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = value
        self.update()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(self.button.rect())
        elif event.type() in (QEvent.Type.Enter, QEvent.Type.Leave, QEvent.Type.EnabledChange):
            target = float(event.type() == QEvent.Type.Enter and self.button.isEnabled())
            self.animation.stop()
            if self.reduced:
                self.progress = target
            else:
                self.animation.setStartValue(self.progress)
                self.animation.setEndValue(target)
                self.animation.start()
        return False

    def paintEvent(self, event):
        if self.progress <= 0.:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.color)
        color.setAlphaF(.32 * self.progress)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)


def install_hover_feedback(root, color, reduced=False):
    buttons = root.findChildren(QPushButton) + root.findChildren(QToolButton)
    if isinstance(root, (QPushButton, QToolButton)):
        buttons.append(root)
    for button in buttons:
        if not hasattr(button, '_daisy_hover'):
            button._daisy_hover = HoverFeedback(button)
        feedback = button._daisy_hover
        feedback.color = QColor(color)
        feedback.reduced = bool(reduced)
        if reduced:
            feedback.animation.stop()
            feedback.progress = float(button.underMouse())
