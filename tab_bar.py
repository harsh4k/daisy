"""The open island's tab bar: the chosen page is a pill with its name, the rest are quiet icons.

Choosing a tab opens its page. The chosen tab grows to show its name and the
group stays centred, as in the reference.
"""
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QToolButton, QWidget
import qtawesome as qta

from focus_ring import KeyboardFocusRing
from ui_tokens import font_css

BAR = 36
TOP, BOTTOM = 4, 4
HEIGHT = TOP + BAR + BOTTOM
# (feature, icon, label): the order the tabs read.
TABS = (('dashboard', 'ph.house', 'Home'), ('music', 'ph.music-notes', 'Music'),
        ('calendar', 'ph.check-square', 'Tasks'), ('month', 'ph.calendar-blank', 'Calendar'),
        ('weather', 'ph.cloud-sun', 'Weather'), ('tools', 'ph.timer', 'Tools'))


class TabButton(KeyboardFocusRing, QToolButton):
    pass


class TabBar(QWidget):
    selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('TabBar')
        self.setFixedHeight(HEIGHT)
        self.theme = None
        self.current = 'dashboard'
        row = QHBoxLayout(self)
        row.setContentsMargins(0, TOP, 0, BOTTOM)
        row.setSpacing(4)
        row.addStretch()
        self.buttons = {}
        for key, icon, label in TABS:
            button = TabButton(objectName='Tab')
            button.setCheckable(True)
            button.setFixedHeight(BAR - 4)
            button.setIconSize(QSize(18, 18))
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty('icon_name', icon)
            button.setProperty('label', label)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
            row.addWidget(button)
            self.buttons[key] = button
        row.addStretch()
        self.set_current('dashboard')

    def button(self, key):
        return self.buttons[key]

    def ordered(self):
        return [self.buttons[key] for key, _, _ in TABS]

    def set_current(self, key):
        self.current = key
        for name, button in self.buttons.items():
            on = name == key
            button.setChecked(on)
            button.setText(button.property('label') if on else '')
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if on
                                      else Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._paint()

    def _paint(self):
        if self.theme is None:
            return
        for button in self.buttons.values():
            color = self.theme['text'] if button.isChecked() else self.theme['muted']
            button.setIcon(qta.icon(button.property('icon_name'), color=color))

    def set_theme(self, theme):
        self.theme = t = theme
        self.setStyleSheet(f'''
            QWidget#TabBar {{ background: transparent; }}
            QToolButton#Tab {{ {font_css('tab')} color: {t['text']}; background: transparent;
                border: 1px solid transparent; border-radius: 16px; padding: 0 9px; min-width: 18px; }}
            QToolButton#Tab:hover {{ background: rgba(255, 255, 255, 0.07); }}
            QToolButton#Tab:checked {{ background: rgba(255, 255, 255, 0.17); padding: 0 14px 0 11px; }}
            QToolButton#Tab[keyboard="true"] {{ border-color: {t['accent']}; }}
        ''')
        self._paint()
