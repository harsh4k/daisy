"""A glance on the Now page: a quiet row that opens its own page when chosen."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout
import qtawesome as qta

from media_widgets import ElidedLabel
from ui_tokens import font_css
from focus_ring import KeyboardFocusRing


class GlanceButton(KeyboardFocusRing, QPushButton):
    def __init__(self, key, icon_name, parent=None):
        super().__init__(parent)
        self.key, self.icon_name = key, icon_name
        self._tint = None
        self._chevron = False
        self.setObjectName('Glance')
        self.setFixedHeight(50)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 10, 0)
        row.setSpacing(12)
        self.tile = QLabel(objectName='GlanceTile')
        self.tile.setFixedSize(30, 30)
        self.tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        self.heading = ElidedLabel()
        self.heading.setObjectName('GlanceTitle')
        self.detail = ElidedLabel()
        self.detail.setObjectName('GlanceDetail')
        text.addStretch()
        text.addWidget(self.heading)
        text.addWidget(self.detail)
        text.addStretch()
        self.value = QLabel(objectName='GlanceValue')
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.tile)
        row.addLayout(text, 1)
        row.addWidget(self.value)
        for child in (self.tile, self.heading, self.detail, self.value):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.theme = None

    def set_content(self, title, detail, value='', chevron=False, tint=None):
        self.heading.setText(title)
        self.detail.setText(detail)
        self._chevron, self._tint = chevron, tint
        self.value.setText('' if chevron else value)
        self.setToolTip(f'{title} · {detail}' if detail else title)
        self.setAccessibleName(', '.join(part for part in (title, detail, value) if part))
        self._paint_icons()

    def _paint_icons(self):
        if self.theme is None:
            return
        self.tile.setPixmap(qta.icon(self.icon_name, color=self._tint or self.theme['text']).pixmap(16, 16))
        if self._chevron:
            self.value.setPixmap(qta.icon('ph.caret-right', color=self.theme['muted']).pixmap(14, 14))

    def set_theme(self, theme):
        self.theme = t = theme
        self.setStyleSheet(f'''
            QPushButton#Glance {{ background: transparent; border: 1px solid transparent; border-radius: 14px; padding: 0;
                text-align: left; min-height: 48px; max-height: 48px; }}
            QPushButton#Glance:hover {{ background: {t['surface']}; }}
            QPushButton#Glance:pressed {{ background: {t['hover']}; }}
            QPushButton#Glance[keyboard="true"] {{ border-color: {t['accent']}; }}
            QLabel#GlanceTile {{ background: {t['surface']}; border-radius: 10px; }}
            QLabel#GlanceTitle {{ {font_css('title')} color: {t['text']}; background: transparent; }}
            QLabel#GlanceDetail {{ {font_css('secondary')} color: {t['muted']}; background: transparent; }}
            QLabel#GlanceValue {{ {font_css('body')} font-size: 15px; font-weight: 500; color: {t['text']}; background: transparent; }}
        ''')
        self._paint_icons()
