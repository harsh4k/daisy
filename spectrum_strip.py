"""The Now page's visualiser: a row of bars that move with what is playing.

It only draws what it is given (audio_spectrum.py). With no sound, or with reduced
motion, it rests as a quiet row of dots.
"""
import time

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QWidget

FRESH = .4   # seconds a set of levels stays on screen without a newer one


class SpectrumStrip(QWidget):
    def __init__(self, bars=24, parent=None):
        super().__init__(parent)
        self.bars = bars
        self.setFixedSize(bars * 6 + 2, 36)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName('Audio visualiser')
        self.tint = QColor('#8e9bff')
        self.levels = [0.] * bars
        self._stamp = 0.

    def set_tint(self, tint):
        color = QColor(tint)
        if color.isValid() and color != self.tint:
            self.tint = color
            self.update()

    def set_levels(self, levels):
        """Bar heights from 0 to 1; an empty list means the sound stopped."""
        self.levels = (list(levels) + [0.] * self.bars)[:self.bars] if levels else [0.] * self.bars
        self._stamp = time.monotonic() if levels else 0.
        self.update()

    def live(self):
        return time.monotonic() - self._stamp < FRESH

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        live = self.live()
        mid, slot, width = self.height() / 2., self.width() / self.bars, 3.4
        for i in range(self.bars):
            level = self.levels[i] if live else 0.
            half = 1.7 + level * (mid - 2.5)      # a resting bar is a dot
            x = i * slot + (slot - width) / 2.
            rect = QRectF(x, mid - half, width, half * 2)
            top, bottom = QColor(self.tint).lighter(135), QColor(self.tint)
            top.setAlphaF(.35 + .65 * level if live else .3)
            bottom.setAlphaF(.25 + .6 * level if live else .22)
            fill = QLinearGradient(0, rect.top(), 0, rect.bottom())
            fill.setColorAt(0., top)
            fill.setColorAt(.5, bottom)
            fill.setColorAt(1., top)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, width / 2., width / 2.)
        painter.end()
