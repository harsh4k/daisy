"""System usage and battery, now a Tools tab rather than the island's first page."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QProgressBar, QVBoxLayout, QGridLayout
import qtawesome as qta

from theme_tokens import get_theme
from ui_tokens import font, font_css


def rate(value):
    value = max(0, value)
    if value < 1024:
        return f'{int(value)} B/s'
    if value < 1024 * 1024:
        return f'{int(value / 1024)} KB/s'
    return f'{value / (1024 * 1024):.1f} MB/s'


class SystemCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('SystemCard')
        self.setAccessibleName('System usage')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(14)
        self.metric_values, self.metric_bars = {}, {}
        for row, (key, title) in enumerate([('cpu', 'CPU'), ('ram', 'Memory'), ('disk', 'Disk')]):
            grid.addWidget(QLabel(title, objectName='Muted'), row, 0)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(4)
            bar.setAccessibleName(title + ' usage')
            value = QLabel('—', objectName='MetricValue')
            value.setFont(font('metric'))
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            value.setMinimumWidth(40)
            grid.addWidget(bar, row, 1)
            grid.addWidget(value, row, 2)
            self.metric_bars[key], self.metric_values[key] = bar, value
        # An unknown battery stays hidden.
        self.battery_row = len(self.metric_values)
        self.battery_icon = QLabel()
        self.battery_icon.setFixedSize(14, 14)
        self.battery_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.battery_icon.setProperty('daisyIcon', 'ph.battery-medium')
        self.battery_icon.setAccessibleName('Battery')
        grid.addWidget(self.battery_icon, self.battery_row, 0)
        self.battery_bar = QProgressBar()
        self.battery_bar.setRange(0, 100)
        self.battery_bar.setTextVisible(False)
        self.battery_bar.setFixedHeight(4)
        self.battery_bar.setAccessibleName('Battery level')
        grid.addWidget(self.battery_bar, self.battery_row, 1)
        self.battery_value = QLabel('—', objectName='MetricValue')
        self.battery_value.setFont(font('metric'))
        self.battery_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.battery_value.setMinimumWidth(40)
        grid.addWidget(self.battery_value, self.battery_row, 2)
        for widget in (self.battery_icon, self.battery_bar, self.battery_value):
            widget.hide()
        self.battery_row_visible = False
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.network = QLabel('↓ —   ↑ —', objectName='Muted')
        self.network.setAccessibleName('Network transfer rate')
        layout.addWidget(self.network)
        layout.addStretch()
        self.set_theme(get_theme())

    def update_metrics(self, data):
        for key in self.metric_values:
            value = max(0, min(100, int(data.get(key, 0))))
            self.metric_values[key].setText(f'{value}%')
            self.metric_bars[key].setValue(value)
        self.network.setText(f"↓ {rate(data.get('down', 0))}   ↑ {rate(data.get('up', 0))}")

    def set_battery(self, state):
        """Show the battery level, or hide the row when there is no battery."""
        percent = None if not state else state.get('percent')
        self.battery_row_visible = percent is not None
        for widget in (self.battery_icon, self.battery_bar, self.battery_value):
            widget.setVisible(self.battery_row_visible)
        if percent is None:
            self.battery_value.setText('—')
            return
        percent = max(0, min(100, int(percent)))
        plugged = bool(state.get('plugged'))
        self.battery_bar.setValue(percent)
        self.battery_value.setText(f'{percent}%')
        name = 'ph.battery-low' if percent <= 20 else ('ph.battery-medium' if percent <= 80 else 'ph.battery-high')
        self.battery_icon.setProperty('daisyIcon', name)
        self.battery_icon.setPixmap(qta.icon(name, color=self.theme['text']).pixmap(14, 14))
        label = f'Battery {percent} percent' + (', charging' if plugged else '')
        for widget in (self.battery_icon, self.battery_value, self.battery_bar):
            widget.setToolTip(label)
            widget.setAccessibleName(label)

    def set_theme(self, theme):
        self.theme = t = theme
        if self.battery_row_visible:
            self.battery_icon.setPixmap(qta.icon(self.battery_icon.property('daisyIcon'), color=t['text']).pixmap(14, 14))
        self.setStyleSheet(f'''
            QWidget#SystemCard {{ background: transparent; }}
            QLabel {{ color: {t['text']}; {font_css('body')} background: transparent; border: none; }}
            QLabel#Muted {{ color: {t['muted']}; {font_css('secondary')} }}
            QLabel#MetricValue {{ color: {t['muted']}; {font_css('metric')} }}
            QProgressBar {{ background: {t['hover']}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
        ''')
