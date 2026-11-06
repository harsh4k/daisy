"""The open island's top bar: where you are, then the battery, time and power menu.

It replaces the old icon dock. On Now the crumb simply reads "Now"; on any
other page it becomes "‹ Now" and takes you back.
"""
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton
import qtawesome as qta

from ui_tokens import SPACING, font, font_css
from focus_ring import KeyboardFocusRing

HEIGHT = 44


class CrumbButton(KeyboardFocusRing, QToolButton):
    pass


class StageBar(QWidget):
    home_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('StageBar')
        self.setFixedHeight(HEIGHT)
        self.theme = None
        self.home = True
        row = QHBoxLayout(self)
        # The crumb's text lines up with the page content's 20 px edge.
        row.setContentsMargins(SPACING['outer'] - 6, 8, SPACING['outer'] - 6, 4)
        row.setSpacing(SPACING['control'])
        self.crumb = CrumbButton(objectName='StageCrumb')
        self.crumb.setText('Now')
        self.crumb.setFixedHeight(32)
        self.crumb.setIconSize(QSize(14, 14))
        self.crumb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.crumb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.crumb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.crumb.clicked.connect(self.home_requested)
        row.addWidget(self.crumb)
        row.addStretch()
        self.battery_icon = QLabel(objectName='StageStatus')
        self.battery_icon.setFixedSize(16, 16)
        self.battery_icon.hide()
        self.status = QLabel(objectName='StageStatus')
        self.status.setFont(font('time'))
        self.status.setAccessibleName('Time')
        row.addWidget(self.battery_icon)
        row.addWidget(self.status)
        self.power_slot = row
        self.set_page(True)

    def add_power(self, button):
        button.setFixedSize(32, 32)
        button.setIconSize(QSize(16, 16))
        self.power_slot.addSpacing(4)
        self.power_slot.addWidget(button)

    def set_page(self, home):
        self.home = home
        self.crumb.setProperty('home', home)
        self.crumb.setToolTip('Now' if home else 'Back to Now')
        self.crumb.setAccessibleName('Now' if home else 'Back to Now')
        self._paint()

    def set_status(self, battery, clock):
        percent = None if not battery else battery.get('percent')
        if percent is None:
            self.battery_icon.hide()
            self.status.setText(clock)
            self.status.setAccessibleName(f'Time {clock}')
            return
        percent = max(0, min(100, int(percent)))
        name = 'ph.battery-low' if percent <= 20 else ('ph.battery-medium' if percent <= 80 else 'ph.battery-high')
        self._battery_name = name
        self.battery_icon.show()
        if self.theme is not None:
            self.battery_icon.setPixmap(qta.icon(name, color=self.theme['muted']).pixmap(16, 16))
        self.status.setText(f'{percent}% · {clock}')
        self.status.setAccessibleName(f'Battery {percent} percent, time {clock}')

    def _paint(self):
        if self.theme is None:
            return
        self.crumb.setIcon(QIcon() if self.home else qta.icon('ph.caret-left-bold', color=self.theme['muted'],
                                                              color_active=self.theme['text']))
        self.crumb.style().unpolish(self.crumb)
        self.crumb.style().polish(self.crumb)
        if self.battery_icon.isVisible() and hasattr(self, '_battery_name'):
            self.battery_icon.setPixmap(qta.icon(self._battery_name, color=self.theme['muted']).pixmap(16, 16))

    def set_theme(self, theme):
        self.theme = t = theme
        self.setStyleSheet(f'''
            QWidget#StageBar {{ background: transparent; }}
            QToolButton#StageCrumb {{ {font_css('title')} color: {t['muted']}; background: transparent;
                border: 1px solid transparent; border-radius: 16px; padding: 0 10px 0 6px; }}
            QToolButton#StageCrumb[home="true"] {{ color: {t['text']}; }}
            QToolButton#StageCrumb:hover {{ color: {t['text']}; background: {t['surface']}; }}
            QToolButton#StageCrumb[home="true"]:hover {{ background: transparent; }}
            QToolButton#StageCrumb[keyboard="true"] {{ border-color: {t['accent']}; }}
            QLabel#StageStatus {{ color: {t['muted']}; background: transparent; }}
        ''')
        self._paint()
