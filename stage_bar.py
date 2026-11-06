"""The open island's header: battery on the left, the date and time at the centre,
a menu on the right. The two eyes sit before the date, as in the reference.

Pages are reached from the tab bar below the page, so the header carries no
navigation of its own.
"""
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
import qtawesome as qta

from daisy_eyes import DaisyEyes
from ui_tokens import font, font_css

HEIGHT = 44
SIDE = 104


class StageBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('StageBar')
        self.setFixedHeight(HEIGHT)
        self.theme = None
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 4, 14, 4)
        row.setSpacing(0)
        left = QWidget()
        left.setFixedWidth(SIDE)
        left_row = QHBoxLayout(left)
        left_row.setContentsMargins(6, 0, 0, 0)
        left_row.setSpacing(6)
        self.battery_icon = QLabel(objectName='StageStatus')
        self.battery_icon.setFixedSize(16, 16)
        self.battery_text = QLabel(objectName='StageStatus')
        self.battery_text.setFont(font('time'))
        self.battery_icon.hide()
        self.battery_text.hide()
        left_row.addWidget(self.battery_icon)
        left_row.addWidget(self.battery_text)
        left_row.addStretch()
        centre = QWidget()
        centre_row = QHBoxLayout(centre)
        centre_row.setContentsMargins(0, 0, 0, 0)
        centre_row.setSpacing(4)
        self.eyes = DaisyEyes()
        self.date = QLabel(objectName='StageDate')
        self.status = QLabel(objectName='StageTime')
        self.status.setFont(font('header_time'))
        self.status.setAccessibleName('Time')
        centre_row.addWidget(self.eyes)
        centre_row.addWidget(self.date)
        centre_row.addWidget(self.status)
        right = QWidget()
        right.setFixedWidth(SIDE)
        self.power_slot = QHBoxLayout(right)
        self.power_slot.setContentsMargins(0, 0, 0, 0)
        self.power_slot.addStretch()
        row.addWidget(left)
        row.addStretch()
        row.addWidget(centre)
        row.addStretch()
        row.addWidget(right)

    def add_power(self, button):
        button.setFixedSize(32, 28)
        button.setIconSize(QSize(22, 22))
        self.power_slot.addWidget(button)

    def set_active(self, active):
        """The eyes only run while the header is on screen."""
        self.eyes.set_active(bool(active))

    def set_status(self, battery, clock, date=''):
        self.date.setText(date)
        self.status.setText(clock)
        self.status.setAccessibleName(f'Time {clock}')
        self.date.setVisible(bool(date))
        percent = None if not battery else battery.get('percent')
        if percent is None:
            self.battery_icon.hide()
            self.battery_text.hide()
            return
        percent = max(0, min(100, int(percent)))
        self._battery_name = ('ph.battery-low' if percent <= 20 else
                              'ph.battery-medium' if percent <= 80 else 'ph.battery-high')
        self.battery_text.setText(f'{percent}%')
        self.battery_text.setAccessibleName(f'Battery {percent} percent')
        self.battery_icon.show()
        self.battery_text.show()
        self._paint()

    def _paint(self):
        if self.theme is not None and self.battery_icon.isVisible() and hasattr(self, '_battery_name'):
            self.battery_icon.setPixmap(qta.icon(self._battery_name, color=self.theme['muted']).pixmap(16, 16))

    def set_theme(self, theme):
        self.theme = t = theme
        self.setStyleSheet(f'''
            QWidget#StageBar {{ background: transparent; }}
            QLabel#StageDate {{ {font_css('header')} color: {t['muted']}; background: transparent; }}
            QLabel#StageTime {{ {font_css('header_time')} color: {t['text']}; background: transparent; }}
            QLabel#StageStatus {{ color: {t['muted']}; background: transparent; }}
        ''')
        self._paint()
