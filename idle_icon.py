"""Small, pausable native idle decorations; no media logos or network access."""
import math
from pathlib import Path
import time

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QMovie, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QLabel
import qtawesome as qta

from branding import resource_path
import aurora

ICON_STYLES = ('Aurora', 'Clock', 'Orbit', 'Pulse', 'Wave', 'Daisy', 'Custom GIF')


class IdleIcon(QLabel):
    """A centered icon that consumes animation time only while in use."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.style_name = 'Clock'
        self.setAccessibleName('Clock idle icon')
        self._custom_path = ''
        self._failed_path = None
        self._color = QColor('white')
        self._tint = QColor('#c1b7d4')
        self._orb = aurora.OrbFrames()
        self._born = time.monotonic()
        self._active = True
        self._reduced_motion = False
        self._phase = 0.0
        self._last_tick = time.monotonic()
        self._movie = None
        self._daisy = QPixmap(resource_path('assets/daisy.png'))
        self._timer = QTimer(self)
        self.loop_timer = self._timer
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._render()

    def _gif_rejected(self, path):
        """Report whether a previously rejected GIF changed on disk."""
        if not self._failed_path or self._failed_path[0] != path:
            return False
        try:
            stamp = Path(path).stat().st_mtime
        except OSError:
            return True
        return stamp == self._failed_path[1]

    def set_style(self, name, custom_path=''):
        """Apply a choice, returning False with a Clock fallback if invalid."""
        path = str(custom_path or '') if name == 'Custom GIF' else ''
        if name == self.style_name and path == self._custom_path:
            return True
        if name == 'Custom GIF' and path and self._gif_rejected(path):
            # The file was already refused; do not read it again every second.
            return False
        movie = None
        valid = name in ICON_STYLES
        if valid and name == 'Custom GIF':
            try:
                valid = bool(path) and Path(path).is_file()
            except (OSError, ValueError):
                valid = False
            if valid:
                try:
                    data = Path(path).read_bytes()
                    valid = data[:6] in (b'GIF87a', b'GIF89a')
                except (OSError, ValueError):
                    valid = False
                if valid:
                    # A buffer releases the selected file immediately on Windows.
                    buffer = QBuffer()
                    buffer.setData(QByteArray(data))
                    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                    movie = QMovie(buffer, b'gif')
                    buffer.setParent(movie)
                    valid = movie.isValid()
            if not valid and movie is not None:
                movie.deleteLater()
                movie = None
            if not valid and path:
                try:
                    stamp = Path(path).stat().st_mtime
                except OSError:
                    stamp = None
                self._failed_path = (path, stamp)
            else:
                self._failed_path = None
        self._dispose_movie()
        self.style_name = name if valid else 'Clock'
        self._custom_path = path if valid else ''
        self._phase = 0.0
        if movie is not None:
            movie.setParent(self)
            movie.setScaledSize(QSize(20, 20))
            movie.frameChanged.connect(self._movie_frame)
            movie.finished.connect(self._restart_movie)
            self._movie = movie
            movie.jumpToFrame(0)
        self.setAccessibleName(self.style_name + ' idle icon')
        if self._active:
            self._render()
        self._sync_running()
        return valid

    def set_color(self, color):
        value = QColor(color)
        if value.isValid() and value != self._color:
            self._color = value
            if self._active and self._movie is None:
                self._render()

    def set_tint(self, color):
        """The orb's light: the theme accent, or the album colour while music plays."""
        value = QColor(color)
        if value.isValid() and value != self._tint:
            self._tint = value
            if self._active and self.style_name == 'Aurora':
                self._render()

    def set_active(self, active):
        active = bool(active)
        if self._active != active:
            self._active = active
            if active:
                self._render()
        self._sync_running()

    def set_reduced_motion(self, reduced):
        self._reduced_motion = bool(reduced)
        if self._reduced_motion:
            self._phase = 0.0
            if self._movie is not None:
                self._movie.stop()
                self._movie.jumpToFrame(0)
            self._render()
        self._sync_running()

    def _dispose_movie(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie.frameChanged.disconnect(self._movie_frame)
            self._movie.deleteLater()
            self._movie = None

    def _sync_running(self):
        running = self._active and self.isVisible() and not self._reduced_motion
        animated = self.style_name not in ('Clock', 'Custom GIF')
        self._timer.setInterval(aurora.ORB_FPS_MS if self.style_name == 'Aurora' else 33)
        if running and animated:
            if not self._timer.isActive():
                self._last_tick = time.monotonic()
                self._timer.start()
        else:
            self._timer.stop()
        if self._movie is not None:
            if running:
                if self._movie.state() == QMovie.MovieState.NotRunning:
                    self._movie.start()
                else:
                    self._movie.setPaused(False)
            elif self._movie.state() == QMovie.MovieState.Running:
                self._movie.setPaused(True)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_running()

    def hideEvent(self, event):
        self._timer.stop()
        if self._movie is not None:
            self._movie.setPaused(True)
        super().hideEvent(event)

    def _tick(self):
        if not self._active or not self.isVisible() or self._reduced_motion:
            self._sync_running()
            return
        now = time.monotonic()
        self._phase = (self._phase + (now - self._last_tick) / 4.0) % 1.0
        self._last_tick = now
        self._render()

    def _movie_frame(self, _frame):
        if self._active and self.isVisible() and self._movie is not None:
            self.setPixmap(self._movie.currentPixmap())

    def _restart_movie(self):
        if self._movie is not None and self._active and self.isVisible() and not self._reduced_motion:
            self._movie.start()

    def _render(self):
        if self._movie is not None:
            self.setPixmap(self._movie.currentPixmap())
            return
        if self.style_name == 'Clock':
            self.setPixmap(qta.icon('ph.clock', color=self._color).pixmap(20, 20))
            return
        if self.style_name == 'Aurora':
            # Reduced motion keeps one still, lit frame.
            seconds = 2.4 if self._reduced_motion else time.monotonic() - self._born
            self.setPixmap(self._orb.frame(seconds, self.width(), max(1., self.devicePixelRatioF()), self._tint))
            return
        pixmap = QPixmap(40, 40)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._color, 1.6, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        angle = self._phase * 2 * math.pi
        if self.style_name == 'Orbit':
            faint = QColor(self._color)
            faint.setAlphaF(0.3)
            painter.setPen(QPen(faint, 1.2))
            painter.drawEllipse(QRectF(3, 3, 14, 14))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color)
            painter.drawEllipse(QPointF(10 + 7 * math.cos(angle),
                                       10 + 7 * math.sin(angle)), 2.1, 2.1)
            painter.drawEllipse(QPointF(10, 10), 1.8, 1.8)
        elif self.style_name == 'Pulse':
            radius = 5 + 2.5 * math.sin(angle)
            painter.drawEllipse(QPointF(10, 10), radius, radius)
            painter.setBrush(self._color)
            painter.drawEllipse(QPointF(10, 10), 2, 2)
        elif self.style_name == 'Wave':
            for index in range(5):
                height = 3 + 10 * (0.5 + 0.5 * math.sin(angle + index * 0.9))
                x = 4 + index * 3
                painter.drawLine(QPointF(x, 10 - height / 2),
                                 QPointF(x, 10 + height / 2))
        elif self.style_name == 'Daisy':
            painter.translate(10, 10)
            painter.rotate(self._phase * 360)
            painter.drawPixmap(QRectF(-9, -9, 18, 18), self._daisy,
                               QRectF(self._daisy.rect()))
        painter.end()
        self.setPixmap(pixmap)
