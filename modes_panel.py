"""Tools -> Modes: one switch for Gaming mode, one for College mode, and what each one did."""
import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from mode_engine import PROTECTED
from theme_tokens import get_theme
from ui_tokens import font_css

CARDS = (
    ('gaming', 'Gaming', 'ph.game-controller', 'Frees GPU memory, freezes apps you chose, full power.',
     'auto_gaming', 'Turn on when a game starts'),
    ('college', 'College', 'ph.student', 'Moves apps off the NVIDIA GPU and saves battery. 120 Hz stays.',
     'auto_college', 'Turn on when the charger is unplugged'),
)


class ModeCard(QFrame):
    def __init__(self, mode, title, icon, blurb, auto_key, auto_text):
        super().__init__()
        self.mode, self.icon_name, self.auto_key = mode, icon, auto_key
        self.setObjectName('ModeCard')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.icon = QLabel()
        self.icon.setFixedSize(20, 20)
        header.addWidget(self.icon)
        self.title = QLabel(title, objectName='ModeTitle')
        header.addWidget(self.title)
        header.addStretch()
        self.apps = QPushButton(objectName='ModeApps')
        self.apps.setFixedSize(32, 32)
        self.apps.setToolTip(f'Choose the apps {title} mode changes')
        self.apps.setAccessibleName(self.apps.toolTip())
        header.addWidget(self.apps)
        self.switch = QPushButton('Turn on', objectName='ModeSwitch')
        self.switch.setCheckable(True)
        self.switch.setFixedHeight(32)
        self.switch.setMinimumWidth(76)
        self.switch.setAccessibleName(f'{title} mode')
        header.addWidget(self.switch)
        layout.addLayout(header)
        self.blurb = QLabel(blurb, objectName='ModeMuted')
        self.blurb.setWordWrap(True)
        layout.addWidget(self.blurb)
        self.status = QLabel('', objectName='ModeStatus')
        self.status.setWordWrap(True)
        self.status.setAccessibleName(f'{title} mode status')
        layout.addWidget(self.status, 1, Qt.AlignmentFlag.AlignTop)
        self.auto = QCheckBox(auto_text)
        self.auto.setAccessibleName(auto_text)
        layout.addWidget(self.auto)

    def set_state(self, on, busy=False):
        self.switch.blockSignals(True)
        self.switch.setChecked(on)
        self.switch.blockSignals(False)
        self.switch.setEnabled(not busy)
        self.switch.setText('Working…' if busy else ('Turn off' if on else 'Turn on'))
        self.setProperty('active', on)
        self.style().unpolish(self)
        self.style().polish(self)


class ModesPanel(QWidget):
    toggled = pyqtSignal(str, bool)
    auto_changed = pyqtSignal(str, bool)
    choose_apps = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ModesPanel')
        self.setAccessibleName('Gaming and College modes')
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 8, 0, 0)
        row.setSpacing(12)
        self.cards = {}
        for spec in CARDS:
            card = ModeCard(*spec)
            card.switch.toggled.connect(lambda on, mode=spec[0]: self.toggled.emit(mode, on))
            card.auto.toggled.connect(lambda on, key=spec[4]: self.auto_changed.emit(key, on))
            card.apps.clicked.connect(self.choose_apps)
            row.addWidget(card, 1)
            self.cards[spec[0]] = card
        self.set_theme(get_theme())

    def set_active(self, active, busy=False):
        for mode, card in self.cards.items():
            card.set_state(mode == active, busy)

    def set_status(self, mode, text, detail=None):
        card = self.cards[mode]
        card.status.setText(text)
        card.status.setToolTip(detail or text)
        card.blurb.setVisible(not text)

    def set_auto(self, settings):
        for card in self.cards.values():
            card.auto.blockSignals(True)
            card.auto.setChecked(bool(settings.get(card.auto_key)))
            card.auto.blockSignals(False)

    def set_theme(self, theme):
        self.theme = t = theme
        for card in self.cards.values():
            card.icon.setPixmap(qta.icon(card.icon_name, color=t['accent']).pixmap(20, 20))
            card.apps.setIcon(qta.icon('ph.sliders-horizontal', color=t['muted']))
        self.setStyleSheet(f'''
            QFrame#ModeCard {{ background: {t['surface']}; border: 1px solid transparent; border-radius: 16px; }}
            QFrame#ModeCard[active="true"] {{ border-color: {t['accent']}; }}
            QLabel {{ background: transparent; color: {t['text']}; }}
            QLabel#ModeTitle {{ {font_css('title')} }}
            QLabel#ModeMuted {{ {font_css('secondary')} color: {t['muted']}; }}
            QLabel#ModeStatus {{ {font_css('secondary')} color: {t['text']}; }}
            QPushButton#ModeSwitch {{ background: {t['hover']}; border-radius: 16px; padding: 0 12px; }}
            QPushButton#ModeSwitch:checked {{ background: {t['accent']}; color: {t['island']}; }}
            QPushButton#ModeApps {{ background: transparent; border-radius: 16px; }}
            QPushButton#ModeApps:hover {{ background: {t['hover']}; }}
            QCheckBox {{ {font_css('secondary')} color: {t['muted']}; spacing: 6px; }}
        ''')


LISTS = (('gaming_freeze', 'Gaming: freeze'), ('college_freeze', 'College: freeze'),
         ('college_gpu_saving', 'College: Intel GPU'))


class AppChooser(QDialog):
    """Tick the apps each mode touches; offers what is open now plus what was chosen before."""

    def __init__(self, settings, running, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose apps for modes')
        self.settings = dict(settings)
        layout = QVBoxLayout(self)
        note = QLabel('Frozen apps pause until the mode turns off, so pick ones you will not switch to. '
                      'Intel GPU choices apply the next time an app opens. Windows, Daisy, AI agents, '
                      'Discord, Riot and Valorant are never frozen.')
        note.setWordWrap(True)
        layout.addWidget(note)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.lists = {}
        for key, label in LISTS:
            chosen = {name.casefold(): name for name in self.settings.get(key, [])}
            offered = dict(chosen)
            for name in running:
                if name.casefold() not in PROTECTED or key == 'college_gpu_saving':
                    offered.setdefault(name.casefold(), name)
            view = QListWidget()
            view.setAccessibleName(label)
            for folded, name in sorted(offered.items()):
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if folded in chosen else Qt.CheckState.Unchecked)
                view.addItem(item)
            tabs.addTab(view, label)
            self.lists[key] = view
        t = get_theme()
        self.setStyleSheet(f'''
            QListWidget::item {{ min-height: 28px; padding: 2px 8px; margin: 0px; border-radius: 6px; }}
            QListWidget::indicator {{ width: 14px; height: 14px; border: 1px solid {t['muted']}; border-radius: 4px; }}
            QListWidget::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}
        ''')
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(420, 420)

    def chosen(self):
        result = dict(self.settings)
        for key, view in self.lists.items():
            result[key] = [view.item(i).text() for i in range(view.count())
                           if view.item(i).checkState() == Qt.CheckState.Checked]
        return result
