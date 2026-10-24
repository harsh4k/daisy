"""A bounded, deduplicated inbox for the notifications Windows already published.

Only notifications that an app published to the Windows notification centre are
visible here. Daisy never reads an application's own storage.
"""
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from ui_tokens import font, font_css

MAX_ITEMS = 60
DEDUPE_SECONDS = 300


class NotificationRecord:
    """One notification, exactly as Windows published it."""

    __slots__ = ('identifier', 'app_id', 'app_name', 'title', 'body', 'timestamp', 'read')

    def __init__(self, identifier='', app_id='', app_name='', title='', body='',
                 timestamp=None):
        self.identifier = identifier or ''
        self.app_id = app_id or ''
        self.app_name = app_name or 'Unknown app'
        self.title = title or ''
        self.body = body or ''
        self.timestamp = time.monotonic() if timestamp is None else timestamp
        self.read = False

    def key(self):
        """The identity used for deduplication."""
        return (self.app_id.lower(), self.title.strip().lower(), self.body.strip().lower())

    def is_duplicate_of(self, other):
        return (self.key() == other.key()
                and abs(self.timestamp - other.timestamp) < DEDUPE_SECONDS)


class NotificationInbox(QWidget):
    """Keeps recent notifications and lets the reader triage them."""

    changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName('Notification inbox')
        self._records = []
        self._filter = ''
        self._text = '#f4f1fa'
        self._muted = '#9a9aa2'
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel('Inbox')
        self.title_label.setFont(font('section'))
        self.count_label = QLabel('0 unread')
        self.count_label.setFont(font('secondary'))
        self.filter_combo = QComboBox()
        self.filter_combo.setAccessibleName('Filter by app')
        self.filter_combo.addItem('All apps', '')
        self.filter_combo.setMaximumWidth(140)
        self.filter_combo.currentIndexChanged.connect(self._filter_changed)
        self.read_button = QPushButton('Mark read')
        self.read_button.setFixedHeight(26)
        self.read_button.clicked.connect(self.mark_all_read)
        self.clear_button = QPushButton('Clear')
        self.clear_button.setFixedHeight(26)
        self.clear_button.clicked.connect(self.clear)
        header.addWidget(self.title_label)
        header.addWidget(self.count_label)
        header.addStretch()
        header.addWidget(self.filter_combo)
        header.addWidget(self.read_button)
        header.addWidget(self.clear_button)
        root.addLayout(header)

        self.list = QListWidget()
        self.list.setAccessibleName('Notifications')
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list.setWordWrap(True)
        self.list.setStyleSheet(f'''
            QListWidget {{ background: transparent; border: none; }}
            QListWidget::item {{ background: transparent; border: none; padding: 3px 2px; }}
            QListWidget::item:selected {{ background: transparent; }}
        ''')
        root.addWidget(self.list, 1)

        self.empty_label = QLabel('No notifications yet.')
        self.empty_label.setFont(font('secondary'))
        self.empty_label.setWordWrap(True)
        self.empty_label.setVisible(False)
        root.addWidget(self.empty_label)

        self.note = QLabel('Only notifications published to Windows are shown.')
        self.note.setFont(font('caption'))
        self.note.setWordWrap(False)
        self.note.setMaximumHeight(16)
        root.addWidget(self.note)

    # -- store ------------------------------------------------------------
    def add(self, record):
        """Add a notification, ignoring a repeat of one already held."""
        if any(record.is_duplicate_of(existing) for existing in self._records):
            return False
        self._records.insert(0, record)
        del self._records[MAX_ITEMS:]
        self._sync_apps()
        self.refresh()
        self.changed.emit(self.unread_count())
        return True

    def records(self):
        return list(self._records)

    def unread_count(self):
        return sum(1 for record in self._records if not record.read)

    def mark_all_read(self):
        for record in self._records:
            record.read = True
        self.refresh()
        self.changed.emit(self.unread_count())

    def clear(self):
        self._records = []
        self._sync_apps()
        self.refresh()
        self.changed.emit(0)

    def set_access_note(self, text):
        """Explain why notifications are unavailable, without hiding the feature."""
        self.note.setText(text)

    # -- view -------------------------------------------------------------
    def _filter_changed(self, _index):
        self._filter = self.filter_combo.currentData() or ''
        self.refresh()

    def _sync_apps(self):
        apps = sorted({record.app_name for record in self._records})
        current = self.filter_combo.currentData()
        existing = [self.filter_combo.itemText(i) for i in range(self.filter_combo.count())]
        if existing == ['All apps'] + apps:
            return
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem('All apps', '')
        for app in apps:
            self.filter_combo.addItem(app, app)
        index = self.filter_combo.findData(current)
        self.filter_combo.setCurrentIndex(max(0, index))
        self.filter_combo.blockSignals(False)

    def refresh(self):
        self.list.clear()
        shown = 0
        for record in self._records:
            if self._filter and record.app_name != self._filter:
                continue
            shown += 1
            item = QListWidgetItem(self._describe(record))
            item.setToolTip(f'{record.app_name}\n{record.title}\n{record.body}')
            item.setData(Qt.ItemDataRole.UserRole, record.identifier)
            item.setForeground(QColor(self._text if not record.read else self._muted))
            self.list.addItem(item)
        unread = self.unread_count()
        self.count_label.setText('0 unread' if unread == 0 else f'{unread} unread')
        self.empty_label.setVisible(shown == 0)
        self.read_button.setEnabled(unread > 0)
        self.clear_button.setEnabled(bool(self._records))

    def set_theme(self, theme):
        """Follow the shell's palette."""
        self._text = theme.get('text', '#f4f1fa')
        self._muted = theme.get('muted', '#9a9aa2')
        self.refresh()

    def _describe(self, record):
        parts = [record.app_name]
        if record.title:
            parts.append(record.title)
        if record.body:
            parts.append(record.body)
        return ' — '.join(parts)
