"""Accessible fixed media text, seek gestures and source selection."""
import math
from PyQt6.QtCore import Qt, QTimer, QSignalBlocker, QEvent, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QLabel, QSlider, QComboBox, QStackedWidget, QSizePolicy, QStyle, QStyleOptionSlider


class ElidedLabel(QLabel):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self.full_text = text
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        self.full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self._elide()

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(
            self.full_text, Qt.TextElideMode.ElideRight, max(0, self.width())))

    def resizeEvent(self, event):
        self._elide()
        super().resizeEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.ApplicationFontChange):
            self._elide()


class SeekSlider(QSlider):
    """A thin neutral line, like the macOS Now Playing scrubber.

    The played part is not painted in the brand colour: it is a brighter
    neutral, and the handle only appears while the pointer is over it.
    """

    keyboard_seek = pyqtSignal()

    def __init__(self):
        super().__init__(Qt.Orientation.Horizontal)
        self.setRange(0, 1000)
        self.setSingleStep(10)
        self.setPageStep(50)
        self.setFixedHeight(32)
        self.setAccessibleName('Playback position')
        self.setToolTip('Seek with arrow keys or drag the position')
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._track_color = QColor(255, 255, 255, 56)
        self._played_color = QColor(255, 255, 255, 191)
        self._hovered = False

    def set_theme(self, theme):
        self._track_color = QColor(theme['text'])
        self._track_color.setAlphaF(0.22)
        self._played_color = QColor(theme['text'])
        self._played_color.setAlphaF(0.78)
        self.update()

    def _groove_rect(self):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        return self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                            QStyle.SubControl.SC_SliderGroove, self)

    def _ratio(self):
        span = self.maximum() - self.minimum()
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.value() - self.minimum()) / span))

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        groove = self._groove_rect()
        if groove.isEmpty():
            super().paintEvent(event)
            return
        active = self._hovered or self.isSliderDown()
        thickness = 5.0 if active else 3.0
        centre = self.height() / 2.0
        track = QRectF(groove.x(), centre - thickness / 2.0, groove.width(), thickness)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._track_color)
        painter.drawRoundedRect(track, thickness / 2.0, thickness / 2.0)
        ratio = self._ratio()
        if ratio > 0:
            played = QRectF(track)
            played.setWidth(max(thickness, track.width() * ratio))
            painter.setBrush(self._played_color)
            painter.drawRoundedRect(played, thickness / 2.0, thickness / 2.0)
        if active:
            handle_x = track.left() + track.width() * ratio
            painter.setBrush(self._played_color)
            painter.drawEllipse(QPointF(handle_x, centre), 6.0, 6.0)
        painter.end()


    def keyPressEvent(self, event):
        before = self.value()
        super().keyPressEvent(event)
        if self.isEnabled() and self.value() != before:
            self.keyboard_seek.emit()

    def _pointer_value(self, event):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                            QStyle.SubControl.SC_SliderHandle, self)
        groove = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                            QStyle.SubControl.SC_SliderGroove, self)
        x = round(event.position().x()) - getattr(self, '_press_offset', 0)
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                             x - groove.x() - handle.width() // 2,
                                             max(1, groove.width() - handle.width()), option.upsideDown)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                            QStyle.SubControl.SC_SliderHandle, self)
        self._press_offset = round(event.position().x()) - handle.center().x() if handle.contains(event.position().toPoint()) else 0
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setSliderDown(True)
        self.setValue(self._pointer_value(event))
        event.accept()

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and self.isEnabled():
            self.setValue(self._pointer_value(event))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.setValue(self._pointer_value(event))
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


def clock(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes}:{seconds:02d}'


class MediaControls:
    def _build_source_picker(self, layout):
        self._active, self._duration = False, 0.
        self._capabilities = dict.fromkeys(('previous', 'play_pause', 'next', 'seek'), False)
        self._preferred_source, self._sources = '', []
        self.source_stack = QStackedWidget()
        self.source_stack.setFixedHeight(22)
        self.source_picker = QComboBox(self)
        self.source_picker.hide()
        self.source_picker.setMinimumWidth(0)
        self.source_picker.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.source_picker.setAccessibleName('Preferred media source')
        self.transport_status = ElidedLabel('')
        self.transport_status.setObjectName('Muted')
        self.source_stack.addWidget(QLabel())
        self.source_stack.addWidget(self.transport_status)
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self._hide_transport_status)
        self.source_picker.currentIndexChanged.connect(self._source_selected)
        self.set_sources([])
        layout.addWidget(self.source_stack)

    def _hide_transport_status(self):
        self.source_stack.setCurrentIndex(0)

    def _source_selected(self, index):
        self._preferred_source = self.source_picker.itemData(index) or ''
        self.preferred_source_requested.emit(self._preferred_source)

    def set_preferred_source(self, source_id):
        self._preferred_source = str(source_id or '')
        self.set_sources(self._sources)

    def set_sources(self, sources):
        self._sources = list(sources)
        blocker = QSignalBlocker(self.source_picker)
        self.source_picker.clear()
        self.source_picker.addItem('Automatic', '')
        for source in sources:
            self.source_picker.addItem(str(source['name']), str(source['id']))
        index = self.source_picker.findData(self._preferred_source)
        if index < 0:
            self.source_picker.addItem(self._preferred_source + ' (unavailable)', self._preferred_source)
            index = self.source_picker.count() - 1
        self.source_picker.setCurrentIndex(index)
        del blocker

    def set_capabilities(self, capabilities):
        self._capabilities = {key: capabilities.get(key) is True for key in self._capabilities}
        self._refresh_control_state()

    def _refresh_control_state(self):
        for button, action in ((self.prev, 'previous'), (self.play, 'play_pause'), (self.next, 'next')):
            button.setEnabled(self._active and self._capabilities[action])
        self.progress.setEnabled(self._active and self._capabilities['seek'] and self._duration > 0)

    def _submit_seek(self):
        if self.progress.isEnabled() and self._duration > 0:
            self.seek_requested.emit(self.progress.value() / 1000 * self._duration)

    def _cancel_seek(self):
        self._duration = 0.
        blocker = QSignalBlocker(self.progress)
        self.progress.setSliderDown(False)
        self.progress.setValue(0)
        del blocker
        self._refresh_control_state()

    def update_timeline(self, position, duration):
        valid = (isinstance(position, (float, int)) and isinstance(duration, (float, int))
                 and math.isfinite(position) and math.isfinite(duration) and duration > 0)
        self._duration = float(duration) if valid else 0.
        if not valid:
            self._cancel_seek()
        self._refresh_control_state()
        if self.progress.isSliderDown() and valid:
            return
        position = max(0., min(position, duration)) if valid else 0.
        self.elapsed.setText(clock(position) if valid or not self._active else '—')
        self.duration.setText(clock(duration) if valid else ('—' if self._active else '0:00'))
        self.progress.setValue(int(position / duration * 1000) if valid else 0)
        self.progress.setAccessibleDescription(
            f'{clock(position)} of {clock(duration)}' if valid else 'Playback position unavailable')

    def show_transport_result(self, action, success):
        names = {'previous': 'Previous track', 'next': 'Next track', 'play_pause': 'Playback', 'seek': 'Seek'}
        message = names.get(action, 'Playback') + (' updated' if success else ' unavailable')
        self.transport_status.setText(message)
        self.source_stack.setCurrentIndex(1)
        self.status_timer.start(2200)
