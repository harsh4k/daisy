"""Animated glowing Daisy Eyes: blinking, glances, a pulse, and moods (emotions.py)."""
import math
import random
import time
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QRadialGradient, QBrush, QPen
from PyQt6.QtWidgets import QWidget

from emotions import EmotionMachine

FULL_HEIGHT = 11.5
EYE_WIDTH = 4.8
SPACING = 6.2  # from the centre to each eye


class DaisyEyes(QWidget):
    """Pair of lively glowing eyes that blink, glance, pulse and show how Daisy feels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Tall enough that the glow fades out inside the widget instead of clipping to a box.
        self.setFixedSize(44, 32)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName("Daisy Eyes")
        self.mood = EmotionMachine()
        self._blink_progress = 0.0  # 0.0 = fully open, 1.0 = closed
        self._is_blinking = False
        self._blink_start = 0.0
        self._blink_duration = 0.16
        self._next_blink = time.monotonic() + random.uniform(2.5, 4.5)
        self._glance_x = self._glance_y = 0.0  # -1.0 to +1.0
        self._target_glance_x = self._target_glance_y = 0.0
        self._glow_color = QColor(220, 245, 255)
        self._eye_color = QColor(255, 255, 255)
        self._reduced_motion = False
        self._is_active = True
        self._audio_active = False
        self._last_tick = time.monotonic()
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(25)  # 40 fps
        self._anim_timer.timeout.connect(self._tick)
        self.mood.step(0, instant=True)

    # -- moods ---------------------------------------------------------------
    @property
    def emotion(self):
        return self.mood.current()

    def react(self, name, seconds=None):
        """Feel something for a while (or until release(name)); the face follows."""
        self.mood.react(name, seconds)
        self._follow_mood()

    def release(self, name):
        self.mood.release(name)
        self._follow_mood()

    def set_hour(self, hour):
        """Night makes the eyes sleepy; the baseline changes with the clock."""
        self.mood.set_hour(hour)
        self._follow_mood()

    def _follow_mood(self):
        if not (self._anim_timer.isActive()):
            self.mood.step(0, instant=True)  # nothing is running to ease it: jump
        self.update()

    # -- animation -----------------------------------------------------------
    def _sync_timer(self):
        """Animate only while the eyes can be seen, are wanted and motion is allowed."""
        run = self.isVisible() and self._is_active and not self._reduced_motion
        if run and not self._anim_timer.isActive():
            self._last_tick = time.monotonic()
            self._anim_timer.start()
        elif not run and self._anim_timer.isActive():
            self._anim_timer.stop()
            self.mood.step(0, instant=True)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_timer()

    def set_reduced_motion(self, reduced: bool):
        self._reduced_motion = bool(reduced)
        if self._reduced_motion:
            self._blink_progress = 0.0
            self._is_blinking = False
        self._sync_timer()
        self._follow_mood()

    def set_active(self, active: bool):
        self._is_active = bool(active)
        self._sync_timer()
        self.update()

    def set_audio_active(self, active: bool, tint=None):
        self._audio_active = bool(active)
        c = QColor(tint) if tint is not None else QColor()
        self._glow_color = c.lighter(130) if c.isValid() else QColor(220, 245, 255)
        self.update()

    def set_ambient_tint(self, tint):
        if tint is not None:
            c = QColor(tint)
            if c.isValid():
                self._glow_color = c
                self.update()

    def look_towards(self, cursor_global_pos):
        """Make eyes subtly glance toward the mouse cursor."""
        if self._reduced_motion or not self.isVisible():
            return
        local = self.mapFromGlobal(cursor_global_pos)
        dx = (local.x() - self.width() / 2.0) / max(1.0, self.width())
        dy = (local.y() - self.height() / 2.0) / max(1.0, self.height())
        self._target_glance_x = max(-1.0, min(1.0, dx * 1.5))
        self._target_glance_y = max(-0.8, min(0.8, dy * 1.5))

    def _tick(self):
        now = time.monotonic()
        self.mood.step(now - self._last_tick)
        self._last_tick = now
        sleepy = self.emotion == 'sleepy'
        happy = self.mood.params['smile'] > .5   # happy eyes are already "closed"
        if not self._is_blinking and now >= self._next_blink and not happy:
            self._is_blinking = True
            self._blink_start = now
            # Sleepy blinks are slow and heavy.
            self._blink_duration = random.uniform(.34, .5) if sleepy else random.uniform(.14, .18)
        if self._is_blinking:
            phase = (now - self._blink_start) / self._blink_duration
            if phase >= 1.0:
                self._is_blinking = False
                self._blink_progress = 0.0
                double = random.random() < .2 and not sleepy
                self._next_blink = now + (.15 if double else random.uniform(4., 7.) if sleepy
                                          else random.uniform(2.8, 5.2))
            else:
                self._blink_progress = 1.0 - abs(phase * 2.0 - 1.0)  # triangular 0 -> 1 -> 0
        self._glance_x += (self._target_glance_x - self._glance_x) * 0.2
        self._glance_y += (self._target_glance_y - self._glance_y) * 0.2
        self.update()

    # -- painting ------------------------------------------------------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        face = self.mood.params
        moving = not self._reduced_motion
        now = time.monotonic()
        cx, cy = self.width() / 2.0, self.height() / 2.0
        wide, lid, smile = face['wide'], face['lid'], max(0., min(1., face['smile']))
        height = FULL_HEIGHT * wide * max(.08, 1. - self._blink_progress * .92)
        height *= 1. - lid * .55
        droop = FULL_HEIGHT * wide * lid * .55 / 2.   # the top lid sags: the bottom edge stays
        bob = face['bounce'] * math.sin(now * 8.) if moving else 0.
        pulse = 1. + (.06 * math.sin(now * (3.5 if self._audio_active else 1.8)) if moving else 0.)
        for sign in (-1, 1):
            ex = cx + sign * SPACING * wide + self._glance_x * 2.0
            ey = cy + self._glance_y * 1.5 + droop + face['lift'] + bob
            self._glow(painter, ex, ey, EYE_WIDTH * pulse * wide, height, 1. - self._blink_progress)
            painter.save()
            painter.translate(ex, ey)
            painter.rotate(sign * face['tilt'])
            if smile < 1.:  # the round eye fades out as the happy arc fades in
                painter.setOpacity(1. - smile)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._eye_color))
                rect = QRectF(-EYE_WIDTH * pulse * wide / 2., -height / 2., EYE_WIDTH * pulse * wide, height)
                radius = min(rect.width() / 2., rect.height() / 2.)
                painter.drawRoundedRect(rect, radius, radius)
            if smile > 0.:
                painter.setOpacity(smile)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(self._eye_color, 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                arc = QPainterPath()
                arc.moveTo(-3.6 * wide, 2.2)
                arc.quadTo(0., -5.2 * wide, 3.6 * wide, 2.2)   # a happy ^
                painter.drawPath(arc)
            painter.restore()
        if face['sparkle'] > .02:
            self._sparkle(painter, cx + SPACING * wide + 6., cy - 9. + face['lift'], face['sparkle'], now if moving else 0.)
        if face['zzz'] > .02:
            self._zzz(painter, cx + SPACING + 7., cy - 3., face['zzz'], now if moving else 0.)
        painter.end()

    def _glow(self, painter, ex, ey, width, height, strength):
        """A soft glow that fades out inside the widget, never as a clipped box."""
        radius = min(max(width, height) * 1.6, self.height() / 2.0 - 1)
        glow = QRadialGradient(QPointF(ex, ey), radius)
        c = self._glow_color
        alpha = int(90 * max(0., strength))
        glow.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
        glow.setColorAt(0.6, QColor(c.red(), c.green(), c.blue(), int(alpha * .35)))
        glow.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(ex, ey), radius, radius)

    def _sparkle(self, painter, x, y, amount, t):
        """A small four-point star that twinkles: Daisy is proud."""
        size = (2.6 + .8 * math.sin(t * 6.)) * amount
        star = QPainterPath()
        for i in range(8):
            r = size if i % 2 == 0 else size * .32
            angle = math.pi / 4 * i - math.pi / 2
            point = QPointF(x + r * math.cos(angle), y + r * math.sin(angle))
            star.moveTo(point) if i == 0 else star.lineTo(point)
        star.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 236, 160, int(235 * amount)))
        painter.drawPath(star)

    def _zzz(self, painter, x, y, amount, t):
        """Two z letters drift up and fade, one after the other: Daisy is dozing."""
        font = QFont(self.font())
        font.setPixelSize(8)
        font.setItalic(True)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        for i in range(2):
            phase = ((t * .45 + i * .5) % 1.) if t else .25 + i * .3
            painter.setPen(QColor(200, 215, 255, int(190 * amount * math.sin(phase * math.pi))))
            painter.drawText(QPointF(x + phase * 3., y - phase * 9.), 'z')
