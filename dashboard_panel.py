"""The open island's Home page: three washed cards, side by side.

Next task, music and focus, each one tap from its own page. Music keeps the one
control worth having here, the play disc. Everything else (date, weather,
calendar, the tools) lives a tab away in the bar below the page.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from home_card import HomeCard, PlayDisc, MUSIC_SIZES
from music_page import rounded
from theme_tokens import get_theme

WASH_TASK = '#1456d9'
WASH_MUSIC = '#b0303c'
WASH_FOCUS = '#8f5bd6'
CARD_GAP = 12
ART = 54


class DashboardPanel(QWidget):
    action_requested = pyqtSignal(str)
    glance_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Dashboard')
        self.setFixedSize(568, 176)
        self.setAccessibleName('Home: next task, music and focus')
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(CARD_GAP)
        self.glances = {key: HomeCard(key) for key in ('calendar', 'music', 'tools')}
        for key, card in self.glances.items():
            card.clicked.connect(lambda _=False, k=key: self.glance_requested.emit(k))
            row.addWidget(card, 1)
        self.play = PlayDisc()
        self.play.setAccessibleName('Play or pause')
        self.play.setToolTip('Play or pause')
        self.play.clicked.connect(lambda: self.action_requested.emit('play_pause'))
        self.glances['music'].set_control(self.play)
        self.glances['music'].title_sizes = MUSIC_SIZES
        self._media = ('Idle', '', '', '')
        self._art = QPixmap()
        self.set_theme(get_theme())
        self.set_next_task(None, 0)
        self.set_focus('25:00', 'Ready · 25 min', False)
        self.update_media('Idle', '', '', '')

    def set_available_width(self, width):
        self.setFixedWidth(min(568, max(0, width)))

    def set_theme(self, theme):
        self.theme = theme
        for card in self.glances.values():
            card.set_theme(theme)

    def set_next_task(self, task, count):
        card = self.glances['calendar']
        if task:
            card.set_content('Next up', task['name'], f"Today · {task['time']}", 'check', WASH_TASK)
        else:
            card.set_content('Next up', 'All clear', 'No more tasks today' if count == 0 else f'{count} on your list',
                             'check', WASH_TASK)

    def set_focus(self, clock, detail, running):
        self.glances['tools'].set_content('Focus', clock, detail, 'stop' if running else 'play', WASH_FOCUS,
                                          numeric=True)

    def update_media(self, state, title, artist, accent):
        self._media = (state, title, artist, accent)
        active = state in ('Playing', 'Paused') and bool(title)
        if active:
            detail = 'paused' if state == 'Paused' else (artist or 'Playing')
            heading = title
        else:
            heading, detail = 'Nothing playing', 'Play something'
        self.play.set_playing(state == 'Playing' and active)
        self.glances['music'].set_content('Music', heading, detail, 'art', self._music_wash(active, accent),
                                          art=self._tile() if active else None)

    def _music_wash(self, active, accent):
        color = QColor(accent) if accent else QColor()
        return color if active and color.isValid() and color.valueF() > .25 else QColor(WASH_MUSIC)

    def _tile(self):
        return None if self._art.isNull() else rounded(self._art, ART, 14)

    def update_artwork(self, data):
        self._art = QPixmap()
        if data:
            self._art.loadFromData(data)
        self.update_media(*self._media)
