"""Small native utilities share one overlay page and the existing theme tokens."""
import math
import qtawesome as qta

from PyQt6.QtCore import Qt, QSize, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPolygonF
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QSpinBox, QTabWidget)
from focus_timer import FocusTimer
from file_shelf import FileShelf
from theme_tokens import get_theme
from ui_tokens import font, font_css


class DurationRuler(QWidget):
    """Decorative minute scale; the adjacent spinbox owns duration input."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.minutes = 25
        self.theme = get_theme()
        self.setFixedHeight(48)
        self.setAccessibleName('Selected duration scale in minutes')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(font('time'))
        spacing = (self.width() - 24) / 20
        for offset in range(-10, 11):
            minute = self.minutes + offset
            if not 1 <= minute <= 180:
                continue
            x = self.width() / 2 + offset * spacing
            major = minute % 5 == 0
            painter.setPen(QColor(self.theme['timer_tick']))
            painter.drawLine(QPointF(x, 24), QPointF(x, 38 if major else 33))
            if major:
                painter.drawText(QRectF(x - 16, 0, 32, 20), Qt.AlignmentFlag.AlignCenter, str(minute))
        x = self.width() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.theme['timer_accent']))
        painter.drawPolygon(QPolygonF([QPointF(x, 39), QPointF(x-4, 46), QPointF(x+4, 46)]))


class ToolsPanel(QWidget):
    shelf_changed = pyqtSignal(list)
    timer_changed = pyqtSignal()
    timer_completed = pyqtSignal()
    dialog_active = pyqtSignal(bool)

    def __init__(self, shelf_paths=None, parent=None):
        super().__init__(parent)
        self.timer = FocusTimer()
        self.completion_pending = False
        self.setAccessibleName('Focus timer and file shelf')
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 4, 24, 4)
        root.setSpacing(8)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self._build_timer()
        self.shelf = FileShelf(shelf_paths)
        self.shelf.changed.connect(self.shelf_changed)
        self.shelf.dialog_active.connect(self.dialog_active)
        self.tabs.addTab(self.shelf, 'File shelf')
        self.set_theme(get_theme())
        self.tick()

    def _build_timer(self):
        page = QWidget()
        page.setObjectName('FocusTimerPage')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        durations = QHBoxLayout()
        durations.setSpacing(4)
        self.preset_buttons = []
        for minutes in (5, 15, 25, 50):
            button = QPushButton(f'{minutes} min')
            button.setFixedSize(56, 32)
            button.setCheckable(True)
            button.setToolTip(f'Start {minutes} minute focus session')
            button.setAccessibleName(button.toolTip())
            button.clicked.connect(lambda _, value=minutes: self.start(value))
            durations.addWidget(button)
            self.preset_buttons.append(button)
        durations.addStretch()
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 180)
        self.minutes.setValue(25)
        self.minutes.setSuffix(' min')
        self.minutes.setAccessibleName('Custom focus duration in minutes')
        self.minutes.setToolTip('Duration for the next session')
        self.minutes.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.minutes.setFixedSize(80, 32)
        durations.addWidget(self.minutes)
        layout.addLayout(durations)
        self.duration_ruler = DurationRuler()
        layout.addWidget(self.duration_ruler)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        summary = QVBoxLayout()
        summary.setSpacing(0)
        self.time_text = QLabel('25:00')
        self.time_text.setObjectName('TimerClock')
        self.time_text.setFont(font('display'))
        self.time_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.time_text.setAccessibleName('Focus timer remaining time')
        summary.addWidget(self.time_text)
        self.state_text = QLabel('Ready to focus')
        self.state_text.setObjectName('TimerState')
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        summary.addWidget(self.state_text)
        self.start_button = QPushButton('Start')
        self.start_button.clicked.connect(lambda: self.start(self.minutes.value()))
        self.pause_button = QPushButton('Pause')
        self.pause_button.clicked.connect(self.toggle_pause)
        self.reset_button = QPushButton('Reset')
        self.reset_button.clicked.connect(self.reset)
        for button, label in ((self.start_button, 'Start focus session'),
                              (self.pause_button, 'Pause focus session'),
                              (self.reset_button, 'Reset focus timer')):
            button.setFixedSize(32, 32)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setIconSize(QSize(20, 20))
            button.setText('')
            button.setObjectName('TimerAction')
            bottom.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.start_button.setObjectName('TimerStart')
        bottom.addStretch()
        bottom.addLayout(summary)
        layout.addLayout(bottom)
        layout.addStretch()
        self.minutes.valueChanged.connect(self.tick)
        self.tabs.addTab(page, 'Focus timer')

    def start(self, minutes):
        self.timer.start(minutes)
        self.completion_pending = False
        self.minutes.setValue(minutes)
        self.tick()
        self.timer_changed.emit()

    def toggle_pause(self):
        if self.timer.state == 'paused':
            self.timer.resume()
        else:
            self.timer.pause()
        self.tick()
        self.timer_changed.emit()

    def reset(self):
        self.timer.reset()
        self.completion_pending = False
        self.tick()
        self.timer_changed.emit()

    def compact_text(self):
        if self.completion_pending:
            return 'Timer done'
        if self.timer.state in ('running', 'paused'):
            seconds = math.ceil(self.timer.remaining())
            return f'{seconds // 60:02d}:{seconds % 60:02d}'
        return ''

    def tick(self):
        self.duration_ruler.minutes = self.minutes.value()
        self.duration_ruler.update()
        for button, minutes in zip(self.preset_buttons, (5, 15, 25, 50)):
            button.setChecked(self.minutes.value() == minutes)
        remaining = math.ceil(self.timer.remaining())
        self.time_text.setText(f'{remaining // 60:02d}:{remaining % 60:02d}' if self.timer.state != 'idle'
                               else f'{self.minutes.value():02d}:00')
        label = 'Resume focus session' if self.timer.state == 'paused' else 'Pause focus session'
        self.pause_button.setToolTip(label)
        self.pause_button.setAccessibleName(label)
        if hasattr(self, '_theme'):
            self.pause_button.setIcon(qta.icon('ph.play-fill' if self.timer.state == 'paused'
                                              else 'ph.pause-fill', color=self._theme['timer_accent']))
        self.pause_button.setEnabled(self.timer.state in ('running', 'paused'))
        self.reset_button.setEnabled(self.timer.state != 'idle')
        self.state_text.setText({'idle': 'Ready to focus', 'running': 'Focusing',
                                 'paused': 'Paused', 'completed': 'Session complete'}[self.timer.state])
        if self.timer.take_completion():
            self.completion_pending = True
            self.timer_completed.emit()
            self.timer_changed.emit()

    def set_theme(self, theme):
        self._theme = theme
        self.duration_ruler.theme = theme
        self.start_button.setIcon(qta.icon('ph.play-fill', color=theme['timer_accent']))
        self.reset_button.setIcon(qta.icon('ph.arrow-counter-clockwise', color=theme['text']))
        self.shelf.set_theme(theme)
        if hasattr(self, 'approvals_panel'):
            self.approvals_panel.set_theme(theme)
        self.tick()
        self.setStyleSheet(f'''
            QWidget {{ color: {theme['text']}; background: transparent; {font_css('body')} }}
            QLabel#TimerClock {{ {font_css('display')} color: {theme['timer_accent']}; }}
            QLabel#TimerState {{ {font_css('secondary')} color: {theme['muted']}; }}
            QPushButton, QSpinBox {{ background: {theme['surface']}; border: 1px solid transparent; border-radius: 8px; padding: 0px; min-height: 30px; max-height: 30px; }}
            QSpinBox {{ border-color: {theme['control_border']}; padding: 0px 8px; }}
            QPushButton:hover {{ background: {theme['hover']}; }}
            QPushButton:checked {{ background: {theme['hover']}; color: {theme['accent']}; }}
            QPushButton:focus, QSpinBox:focus, QListWidget:focus {{ border: 1px solid {theme['accent']}; }}
            QPushButton:disabled {{ color: {theme['muted']}; }}
            QWidget#FocusTimerPage QPushButton {{ background: transparent; color: {theme['muted']}; }}
            QWidget#FocusTimerPage QPushButton:checked {{ color: {theme['timer_accent']}; background: {theme['timer_surface']}; }}
            QWidget#FocusTimerPage QPushButton:hover {{ background: {theme['hover']}; color: {theme['timer_accent']}; }}
            QWidget#FocusTimerPage QPushButton:pressed {{ background: {theme['timer_surface']}; }}
            QWidget#FocusTimerPage QPushButton#TimerAction {{ border-radius: 16px; background: {theme['surface']}; }}
            QWidget#FocusTimerPage QPushButton#TimerStart {{ border-radius: 16px; background: {theme['timer_surface']}; }}
            QWidget#FocusTimerPage QPushButton#TimerAction:hover, QWidget#FocusTimerPage QPushButton#TimerStart:hover {{ background: {theme['hover']}; }}
            QWidget#FocusTimerPage QPushButton#TimerAction:pressed, QWidget#FocusTimerPage QPushButton#TimerStart:pressed {{ background: {theme['timer_surface']}; }}
            QListWidget {{ border: 1px solid {theme['border']}; border-radius: 7px; background: {theme['surface']}; }}
            QListWidget::item:selected {{ background: {theme['hover']}; color: {theme['text']}; }}
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{ background: transparent; color: {theme['muted']}; padding: 8px 4px 6px 4px; margin-right: 16px;
                border: none; border-bottom: 2px solid transparent; }}
            QTabBar::tab:hover {{ color: {theme['text']}; }}
            QTabBar::tab:selected {{ color: {theme['text']}; border-bottom: 2px solid {theme['accent']}; }}
        ''')
