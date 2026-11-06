"""The open island's Now page (Stage): music leads, glances beside it open pages.

There is no dock. What is playing sits on the left with its artwork, scrubber
and transport; four glances on the right (focus, next task, calendar, weather)
each open their own page. System usage lives in Tools → System.
"""
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal
import qtawesome as qta
from PyQt6.QtGui import QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout

from theme_tokens import get_theme
from ui_tokens import font, font_css
from branding import media_icon, media_identity
from media_widgets import ElidedLabel, SeekSlider, MediaControls
from glance import GlanceButton

ART = 96
ART_RADIUS = 18
# Glances in the order they read, each opening a feature page.
GLANCES = (('tools', 'ph.timer'), ('calendar', 'ph.check-square'),
           ('month', 'ph.calendar-blank'), ('weather', 'ph.cloud-sun'))


def rounded(pixmap, size, radius):
    """A centre-cropped square, scaled and clipped to concentric corners."""
    square = min(pixmap.width(), pixmap.height())
    pixmap = pixmap.copy((pixmap.width() - square) // 2, (pixmap.height() - square) // 2, square, square)
    ratio = 2
    scaled = pixmap.scaled(size * ratio, size * ratio, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    result = QPixmap(size * ratio, size * ratio)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size * ratio, size * ratio), radius * ratio, radius * ratio)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    result.setDevicePixelRatio(ratio)
    return result


class DashboardPanel(QWidget, MediaControls):
    action_requested = pyqtSignal(str)
    seek_requested = pyqtSignal(float)
    preferred_source_requested = pyqtSignal(str)
    glance_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Dashboard')
        self.setFixedSize(584, 208)
        self._source_raw, self._media_title, self._artwork_data = '', '', b''
        self.setAccessibleName('Now: music and glances')
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)
        self.media_card = QFrame(objectName='Card')
        self.glance_column = QFrame(objectName='Glances')
        root.addWidget(self.media_card, 1)
        root.addWidget(self.glance_column)
        self._build_media()
        self._build_glances()
        self.set_available_width(584)
        self.set_theme(get_theme())
        self.update_media('Idle', '', '', '')

    def _button(self, action):
        button = QPushButton()
        # Tab reaches the transport; a click does not leave a focus ring behind.
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self.action_requested.emit(action))
        return button

    def _build_media(self):
        grid = QGridLayout(self.media_card)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(0)
        self.artwork = QLabel(objectName='Artwork')
        self.artwork.setFixedSize(ART, ART)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setAccessibleName('Album artwork')
        self.source_badge = QLabel(self.artwork, objectName='SourceBadge')
        self.source_badge.setFixedSize(26, 26)
        self.source_badge.move(ART - 30, ART - 30)
        self.source_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.artwork, 0, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setContentsMargins(0, 2, 0, 0)
        text.setSpacing(2)
        self.eyebrow = QLabel('MUSIC', objectName='Eyebrow')
        eyebrow_font = font('caption')
        eyebrow_font.setWeight(eyebrow_font.Weight.DemiBold)
        eyebrow_font.setLetterSpacing(eyebrow_font.SpacingType.AbsoluteSpacing, .6)
        self.eyebrow.setFont(eyebrow_font)
        self.source = QLabel('MEDIA', objectName='Eyebrow')
        self.source.hide()
        self.title = ElidedLabel('Nothing playing')
        self.title.setObjectName('TrackTitle')
        self.artist = ElidedLabel('Choose something to play')
        self.artist.setObjectName('Muted')
        text.addWidget(self.eyebrow)
        text.addSpacing(4)
        text.addWidget(self.title)
        text.addWidget(self.artist)
        self._build_source_picker(text)
        text.addStretch()
        grid.addLayout(text, 0, 1)
        self.progress = SeekSlider()
        self.progress.sliderReleased.connect(self._submit_seek)
        self.progress.keyboard_seek.connect(self._submit_seek)
        grid.addWidget(self.progress, 1, 0, 1, 2)
        times = QHBoxLayout()
        self.elapsed = QLabel('0:00', objectName='Time')
        self.duration = QLabel('0:00', objectName='Time')
        self.elapsed.setFont(font('time'))
        self.duration.setFont(font('time'))
        times.addWidget(self.elapsed)
        times.addStretch()
        times.addWidget(self.duration)
        grid.addLayout(times, 2, 0, 1, 2)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 2, 0, 0)
        controls.setSpacing(12)
        self.prev, self.play, self.next = self._button('previous'), self._button('play_pause'), self._button('next')
        for button, name in [(self.prev, 'Previous track'), (self.play, 'Play or pause'), (self.next, 'Next track')]:
            button.setAccessibleName(name)
            button.setToolTip(name)
            button.setObjectName('Transport')
            size = 40 if button is self.play else 32
            button.setFixedSize(size, size)
            button.setIconSize(QSize(28, 28) if button is self.play else QSize(20, 20))
            controls.addWidget(button)
        controls.addStretch()
        grid.addLayout(controls, 3, 0, 1, 2)
        grid.setRowStretch(4, 1)
        grid.setColumnStretch(1, 1)

    def _build_glances(self):
        column = QVBoxLayout(self.glance_column)
        column.setContentsMargins(16, 0, 0, 0)
        column.setSpacing(2)
        self.glances = {}
        for key, icon in GLANCES:
            button = GlanceButton(key, icon)
            button.clicked.connect(lambda _, k=key: self.glance_requested.emit(k))
            column.addWidget(button)
            self.glances[key] = button
        column.addStretch()

    def set_glance(self, key, title, detail, value='', chevron=False, tint=None):
        self.glances[key].set_content(title, detail, value, chevron, tint)

    def set_available_width(self, width):
        self.setFixedWidth(min(584, max(0, width)))
        self.glance_column.setFixedWidth(min(268, max(180, int(self.width() * .46))))

    def update_media(self, state, title, artist, accent):
        active = state in ('Playing', 'Paused') and bool(title)
        if (title, artist) != (self._media_title, self.artist.full_text):
            self._cancel_seek()
        self._active = active
        self.eyebrow.setText('NOW PLAYING' if state == 'Playing' and active else ('PAUSED' if active else 'MUSIC'))
        self.title.setText(title if active else 'Nothing playing')
        self.artist.setText(artist if active else 'Choose something to play')
        self._media_title = title if active else ''
        self._refresh_source()
        self._playing = state == 'Playing'
        self._refresh_transport_icons()
        self._refresh_control_state()
        if not active:
            self.update_artwork(b'')
            self.update_timeline(0, 0)

    def update_source(self, source):
        if self._source_raw != (source or ''):
            self._cancel_seek()
        self._source_raw = source or ''
        self._refresh_source()

    def _refresh_source(self):
        name, _kind = media_identity(self._source_raw, self._media_title)
        self.source.setText(name)
        self.source_badge.setAccessibleName(name)
        self.source_badge.setToolTip(name)
        self.source_badge.setPixmap(media_icon(self._source_raw, self._media_title, 22).pixmap(22, 22))
        self.update_artwork(self._artwork_data)

    def update_artwork(self, data):
        self._artwork_data = data
        pixmap = QPixmap()
        if data:
            pixmap.loadFromData(data)
        kind = media_identity(self._source_raw, self._media_title)[1]
        self.source_badge.setVisible(not pixmap.isNull() and kind != 'media')
        if pixmap.isNull():
            self.artwork.setPixmap(media_icon(self._source_raw, self._media_title, 56).pixmap(56, 56))
        else:
            self.artwork.setPixmap(rounded(pixmap, ART, ART_RADIUS))
        self.source_badge.raise_()

    def _refresh_transport_icons(self):
        color = getattr(self, 'theme', get_theme())['text']
        for button, icon in [(self.prev, 'ph.skip-back-fill'), (self.play, 'ph.pause-fill' if getattr(self, '_playing', False) else 'ph.play-fill'), (self.next, 'ph.skip-forward-fill')]:
            button.setText('')
            button.setIcon(qta.icon(icon, color=color))

    def set_theme(self, theme):
        self.theme = t = theme
        self._refresh_transport_icons()
        self.progress.set_theme(theme)
        for button in self.glances.values():
            button.set_theme(theme)
        self.setStyleSheet(f'''
            QWidget#Dashboard {{ background: transparent; }}
            QFrame#Card {{ background: transparent; border: none; }}
            QFrame#Glances {{ background: transparent; border: none; border-left: 1px solid {t['border']}; }}
            QLabel {{ color: {t['text']}; {font_css('body')} background: transparent; border: none; }}
            QLabel#Eyebrow {{ color: {t['muted']}; }}
            QLabel#Muted, QLabel#Time {{ color: {t['muted']}; {font_css('secondary')} }}
            QLabel#TrackTitle {{ {font_css('section')} }}
            QLabel#Time {{ {font_css('time')} }}
            QLabel#Artwork {{ background: {t['surface']}; border-radius: {ART_RADIUS}px; }}
            QLabel#SourceBadge {{ background: {t['island']}; border-radius: 13px; }}
            QPushButton#Transport {{ background: transparent; border: 1px solid transparent; border-radius: 16px; padding: 0; }}
            QPushButton#Transport:hover {{ background: {t['surface']}; }}
            QPushButton#Transport:focus {{ border-color: {t['accent']}; }}
            QSlider {{ background: transparent; border: none; }}
            QSlider::groove:horizontal {{ background: transparent; height: 4px; }}
            QSlider::sub-page:horizontal {{ background: transparent; }}
            QSlider::add-page:horizontal {{ background: transparent; }}
            QSlider::handle:horizontal {{ background: transparent; width: 10px; margin: -4px 0; }}
            QSlider::handle:horizontal:disabled {{ background: transparent; }}
            QSlider:focus {{ border: 1px solid {t['accent']}; border-radius: 4px; }}
            QComboBox {{ color: {t['muted']}; background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 4px; font-size: 10px; padding: 1px 4px; }}
            QComboBox:focus {{ border-color: {t['accent']}; }}
            QComboBox QAbstractItemView {{ background: {t['background']}; color: {t['text']}; selection-background-color: {t['hover']}; }}
        ''')
