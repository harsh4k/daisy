"""Animated glowing Daisy Eyes: natural blinking, pupil glance, and ambient pulse."""
import math
import random
import time
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QRadialGradient, QBrush, QPen
from PyQt6.QtWidgets import QWidget


class DaisyEyes(QWidget):
    """Pair of lively glowing eyes that naturally blink, glance, and pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName("Daisy Eyes")

        self._blink_progress = 0.0  # 0.0 = fully open, 1.0 = closed
        self._is_blinking = False
        self._blink_start = 0.0
        self._blink_duration = 0.16  # 160ms total blink
        self._next_blink = time.monotonic() + random.uniform(2.5, 4.5)

        self._glance_x = 0.0  # -1.0 to +1.0
        self._glance_y = 0.0  # -1.0 to +1.0
        self._target_glance_x = 0.0
        self._target_glance_y = 0.0

        self._glow_color = QColor(220, 245, 255)
        self._eye_color = QColor(255, 255, 255)
        self._reduced_motion = False
        self._is_active = True
        self._audio_active = False

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(25)  # 40 fps
        self._anim_timer.timeout.connect(self._tick)

    def _sync_timer(self):
        """Animate only while the eyes can be seen, are wanted and motion is allowed."""
        run = self.isVisible() and self._is_active and not self._reduced_motion
        if run and not self._anim_timer.isActive():
            self._anim_timer.start()
        elif not run and self._anim_timer.isActive():
            self._anim_timer.stop()

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
        self.update()

    def set_active(self, active: bool):
        self._is_active = bool(active)
        self._sync_timer()
        self.update()

    def set_audio_active(self, active: bool, tint=None):
        self._audio_active = bool(active)
        if tint is not None:
            c = QColor(tint)
            if c.isValid():
                self._glow_color = c.lighter(130)
        else:
            self._glow_color = QColor(220, 245, 255)
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
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        dx = (local.x() - center_x) / max(1.0, self.width())
        dy = (local.y() - center_y) / max(1.0, self.height())
        self._target_glance_x = max(-1.0, min(1.0, dx * 1.5))
        self._target_glance_y = max(-0.8, min(0.8, dy * 1.5))

    def _tick(self):
        now = time.monotonic()

        # Handle natural blinking cycle
        if not self._is_blinking and now >= self._next_blink:
            self._is_blinking = True
            self._blink_start = now
            self._blink_duration = random.uniform(0.14, 0.18)

        if self._is_blinking:
            elapsed = now - self._blink_start
            phase = elapsed / self._blink_duration
            if phase >= 1.0:
                self._is_blinking = False
                self._blink_progress = 0.0
                # Double-blink with 20% probability
                if random.random() < 0.2:
                    self._next_blink = now + 0.15
                else:
                    self._next_blink = now + random.uniform(2.8, 5.2)
            else:
                # Triangular envelope: 0 -> 1 -> 0
                self._blink_progress = 1.0 - abs(phase * 2.0 - 1.0)

        # Smooth glance interpolation
        self._glance_x += (self._target_glance_x - self._glance_x) * 0.2
        self._glance_y += (self._target_glance_y - self._glance_y) * 0.2

        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0

        # Eye parameters
        eye_width = 4.8
        full_height = 11.5
        spacing = 6.2  # distance from center to each eye center

        # Apply blink: squeeze height
        h_scale = max(0.08, 1.0 - self._blink_progress * 0.92)
        current_h = full_height * h_scale

        # Apply subtle glance offset
        glance_px_x = self._glance_x * 2.0
        glance_px_y = self._glance_y * 1.5

        # Ambient gentle breathing pulse (1.0 to 1.08)
        pulse = 1.0
        if not self._reduced_motion:
            t = time.monotonic()
            pulse = 1.0 + 0.06 * math.sin(t * (3.5 if self._audio_active else 1.8))

        for sign in (-1, 1):
            ex = center_x + sign * spacing + glance_px_x
            ey = center_y + glance_px_y
            rect = QRectF(ex - (eye_width * pulse) / 2.0, ey - current_h / 2.0,
                          eye_width * pulse, current_h)

            # Soft luminous outer glow
            if self._blink_progress < 0.7:
                glow_r = max(rect.width(), rect.height()) * 1.6
                glow = QRadialGradient(QPointF(ex, ey), glow_r)
                g_col = QColor(self._glow_color)
                alpha = int(90 * (1.0 - self._blink_progress))
                glow.setColorAt(0.0, QColor(g_col.red(), g_col.green(), g_col.blue(), alpha))
                glow.setColorAt(0.6, QColor(g_col.red(), g_col.green(), g_col.blue(), int(alpha * 0.35)))
                glow.setColorAt(1.0, QColor(g_col.red(), g_col.green(), g_col.blue(), 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(glow))
                painter.drawEllipse(QPointF(ex, ey), glow_r, glow_r)

            # Solid eye core
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._eye_color))
            r_corner = min(rect.width() / 2.0, rect.height() / 2.0)
            painter.drawRoundedRect(rect, r_corner, r_corner)

        painter.end()
