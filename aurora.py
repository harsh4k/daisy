"""The pill's ambient life: a small glass orb with drifting light, and audio bars.

Both are painted directly with QPainter at the screen's pixel ratio, at a low
frame rate, and only while visible. Reduced motion draws one still frame.
"""
import math
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient, QLinearGradient
from PyQt6.QtWidgets import QWidget

ORB_FPS_MS = 50      # 20 fps: the drift is slow, so more frames buy nothing
BARS_FPS_MS = 33     # ~30 fps for the livelier bars
LOOP_SECONDS = 12.   # every light completes whole orbits in this loop, so frames repeat
# Three lights drift inside the orb: (hue shift, seconds per orbit, orbit, size, strength).
# Periods divide the loop (12, -6, 4: the middle one runs backwards).
LIGHTS = ((0., 12., .42, .78, .85), (.11, -6., .5, .66, .7), (-.13, 4., .36, .58, .6))
_FRAMES_PER_LOOP = round(LOOP_SECONDS * 1000 / ORB_FPS_MS)


def vivid(color):
    """Lift muted theme accents so the orb reads as light, not grey."""
    hue, saturation, value, _ = QColor(color).getHsvF()
    hue = 0.72 if hue < 0 else hue  # achromatic accents get a soft violet
    return QColor.fromHsvF(hue, max(saturation, .55), max(value, .92))


def _shift(color, amount):
    hue, saturation, value, _ = color.getHsvF()
    return QColor.fromHsvF((hue + amount) % 1., saturation, value)


def _alpha(color, alpha):
    result = QColor(color)
    result.setAlphaF(max(0., min(1., alpha)))
    return result


def paint_orb(painter, center, radius, seconds, tint):
    """A glass sphere lit from the upper left, with three lights drifting inside."""
    base = vivid(tint)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    halo = QRadialGradient(center, radius * 1.45)
    halo.setColorAt(.55, _alpha(base, .22))
    halo.setColorAt(1., _alpha(base, 0.))
    painter.setBrush(halo)
    painter.drawEllipse(center, radius * 1.45, radius * 1.45)
    body = QRadialGradient(center + QPointF(-.3 * radius, -.35 * radius), radius * 1.5)
    body.setColorAt(0., base.darker(160))
    body.setColorAt(.6, base.darker(330))
    body.setColorAt(1., QColor(base.darker(700)))
    painter.setBrush(body)
    painter.drawEllipse(center, radius, radius)
    sphere = QPainterPath()
    sphere.addEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))
    operation = Qt.ClipOperation.IntersectClip if painter.hasClipping() else Qt.ClipOperation.ReplaceClip
    painter.setClipPath(sphere, operation)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    for index, (shift, period, orbit, size, strength) in enumerate(LIGHTS):
        angle = 2 * math.pi * (seconds / period) + index * 2.1
        point = center + QPointF(math.cos(angle) * orbit * radius, math.sin(angle) * orbit * radius * .8)
        light = _shift(base, shift)
        glow = QRadialGradient(point, size * radius)
        glow.setColorAt(0., _alpha(light, strength))
        glow.setColorAt(1., _alpha(light, 0.))
        painter.setBrush(glow)
        painter.drawEllipse(point, size * radius, size * radius)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    shine = QRadialGradient(center + QPointF(-.38 * radius, -.46 * radius), .6 * radius)
    shine.setColorAt(0., _alpha(QColor('white'), .62))
    shine.setColorAt(1., _alpha(QColor('white'), 0.))
    painter.setBrush(shine)
    painter.drawEllipse(center + QPointF(-.38 * radius, -.46 * radius), .6 * radius, .6 * radius)
    painter.restore()


def bar_levels(seconds, count=4):
    """Lively, never-repeating heights in 0..1 from a few incommensurate waves."""
    levels = []
    for index in range(count):
        wave = (math.sin(seconds * (5.1 + index * 1.7) + index * 1.3) * .5
                + math.sin(seconds * (8.3 + index * .9) + index * 2.7) * .3
                + math.sin(seconds * (2.3 + index * .5)) * .2)
        levels.append(.5 + .5 * wave)
    return levels


def paint_bars(painter, rect, levels, tint, strength=1.):
    """Rounded bars rising from the centre line, lighter at the tips."""
    base = vivid(tint)
    count = len(levels)
    width, gap = 2.6, 2.2
    total = count * width + (count - 1) * gap
    left = rect.center().x() - total / 2
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    for index, level in enumerate(levels):
        height = max(width, (3 + 11 * level) * min(1., rect.height() / 16))
        bar = QRectF(left + index * (width + gap), rect.center().y() - height / 2, width, height)
        fill = QLinearGradient(bar.topLeft(), bar.bottomLeft())
        fill.setColorAt(0., _alpha(base.lighter(130), strength))
        fill.setColorAt(1., _alpha(base, strength * .85))
        painter.setBrush(fill)
        painter.drawRoundedRect(bar, width / 2, width / 2)
    painter.restore()


class OrbFrames:
    """One loop of orb frames, painted once per colour and screen scale, then reused."""

    def __init__(self):
        self._key = None
        self._frames = {}

    def frame(self, seconds, side, ratio, tint):
        key = (QColor(tint).rgba(), side, ratio)
        if key != self._key:
            self._key, self._frames = key, {}
        index = int((seconds % LOOP_SECONDS) / LOOP_SECONDS * _FRAMES_PER_LOOP) % _FRAMES_PER_LOOP
        pixmap = self._frames.get(index)
        if pixmap is None:
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(round(side * ratio), round(side * ratio))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            paint_orb(painter, QPointF(side / 2, side / 2), side * .37,
                      index * LOOP_SECONDS / _FRAMES_PER_LOOP, tint)
            painter.end()
            self._frames[index] = pixmap
        return pixmap


class AudioBars(QWidget):
    """Trailing pill element: live bars while music plays, still while paused."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName('Now playing')
        self.state = 'Idle'
        self.tint = QColor('#c1b7d4')
        self.reduced_motion = False
        self._start = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(BARS_FPS_MS)
        self.timer.timeout.connect(self.update)
        self.setVisible(False)

    def set_state(self, state, tint=None):
        if tint is not None and QColor(tint).isValid():
            self.tint = QColor(tint)
        self.state = state
        self.setVisible(state in ('Playing', 'Paused'))
        self._sync()
        self.update()

    def set_reduced_motion(self, reduced):
        self.reduced_motion = bool(reduced)
        self._sync()
        self.update()

    def _sync(self):
        live = self.isVisible() and self.state == 'Playing' and not self.reduced_motion
        if live and not self.timer.isActive():
            self.timer.start()
        elif not live:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        if self.state == 'Playing' and not self.reduced_motion:
            levels = bar_levels(time.monotonic() - self._start)
            strength = 1.
        else:
            levels = [.35, .6, .45, .3]
            strength = .55 if self.state == 'Paused' else 1.
        paint_bars(painter, QRectF(self.rect()), levels, self.tint, strength)
        painter.end()
