"""Side-effect-free live renderer using the shell's shape and IdleIcon patterns."""
import math
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget

from idle_icon import IdleIcon
from theme_tokens import get_theme
from motion_policy import effective_reduced_motion
from ui_tokens import font


class SettingsPreview(QWidget):
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setAccessibleName('Live Daisy appearance preview')
        self.settings = {}
        self.view = 'Compact'
        self.icon = IdleIcon(self)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self.set_settings(settings or {})

    def set_settings(self, settings):
        self.settings = dict(settings)
        self.theme = get_theme(self.settings.get('theme'), self.settings.get('surface_treatment', 'neutral'))
        self.reduced_motion = effective_reduced_motion(self.settings.get('motion_mode', 'auto'))
        self.icon.set_reduced_motion(self.reduced_motion)
        self.icon.set_color(self.theme['text'])
        self.icon.set_style(self.settings.get('idle_icon', 'Clock'),
                            self.settings.get('custom_idle_icon', ''))
        self._sync_timer()
        self.update()

    def set_view(self, view):
        self.view = view
        self.icon.setVisible(view == 'Compact')
        self._sync_timer()
        self.update()

    def _sync_timer(self):
        if (self.isVisible() and self.view == 'Expanded' and not self.reduced_motion
                and self.settings.get('decorative_effects_enabled', False)
                and self.settings.get('animation_style') != 'None'):
            self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, event):
        self.icon.set_active(True)
        self._sync_timer()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        self.icon.set_active(False)
        super().hideEvent(event)

    def _shape(self, rect):
        path = QPainterPath()
        if self.settings.get('island_style') != 'Notch Nook':
            path.addRoundedRect(rect, min(rect.height() / 2, 30), min(rect.height() / 2, 30))
            return path
        # Mirrors DynamicIsland.build_notch_path, including its scooped top corners.
        radius = min(rect.height() / 2, 18)
        scoop = min(radius * 1.4, 25)
        path.moveTo(rect.left() - scoop, rect.top())
        path.cubicTo(rect.left() - scoop * .05, rect.top(), rect.left(),
                     rect.top() + scoop * .05, rect.left(), rect.top() + scoop)
        path.lineTo(rect.left(), rect.bottom() - radius)
        path.quadTo(rect.left(), rect.bottom(), rect.left() + radius, rect.bottom())
        path.lineTo(rect.right() - radius, rect.bottom())
        path.quadTo(rect.right(), rect.bottom(), rect.right(), rect.bottom() - radius)
        path.lineTo(rect.right(), rect.top() + scoop)
        path.cubicTo(rect.right(), rect.top() + scoop * .05, rect.right() + scoop * .05,
                     rect.top(), rect.right() + scoop, rect.top())
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(self.theme['surface']))
        width = min(320 if self.view == 'Expanded' else 180, self.width() - 64)
        height = 4 if self.view == 'Edge line' else (112 if self.view == 'Expanded' else 40)
        height = min(height, max(40, self.height() - 24))
        rect = QRectF((self.width() - width) / 2, 12, width, height)
        self.icon.setVisible(self.view == 'Compact')
        self.icon.move(int(rect.center().x() - 67), int(rect.center().y() - 11))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.theme['edge_line'] if self.view == 'Edge line' else self.theme['background']))
        shape = self._shape(rect)
        if self.view == 'Edge line':
            rect.setWidth(96)
            rect.moveCenter(QPointF(self.width() / 2, 14))
            p.drawRoundedRect(rect, 2, 2)
            return
        p.drawPath(shape)
        p.save()
        p.setClipPath(shape)
        if self.view == 'Expanded':
            phase = time.monotonic() % 6 / 6 if not self.reduced_motion else 0
            animation = (self.settings.get('animation_style', 'None')
                         if self.settings.get('decorative_effects_enabled', False)
                         and not self.reduced_motion else 'None')
            accent = QColor(self.theme['accent'])
            if animation in ('Fluid Blobs', 'Glow Sweep'):
                center = QPointF(rect.left() + rect.width() * phase, rect.center().y())
                gradient = QRadialGradient(center, rect.width() * .65)
                accent.setAlpha(40)
                gradient.setColorAt(0, accent)
                accent.setAlpha(0)
                gradient.setColorAt(1, accent)
                p.fillRect(rect, gradient)
            elif animation == 'Neon Border':
                accent.setAlphaF(.35 + .25 * math.sin(phase * math.tau))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(accent, 2))
                p.drawPath(shape)
            p.setPen(QColor(self.theme['text']))
            p.setFont(font('title'))
            p.drawText(rect.adjusted(24, 12, -24, 32 - height), 'Now playing')
            p.setPen(QColor(self.theme['muted']))
            p.setFont(font('secondary'))
            p.drawText(rect.adjusted(24, 36, -24, -12), 'Media · Focus · Shelf')
        else:
            p.setPen(QColor(self.theme['text']))
            p.setFont(font('title'))
            p.drawText(rect.adjusted(43, 0, -12, 0), Qt.AlignmentFlag.AlignCenter, 'Wed, 12:27 AM')
        p.restore()

