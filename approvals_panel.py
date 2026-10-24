"""Compact native permission review, following ToolsPanel's theme/font patterns."""
import html
import json
import time

import qtawesome as qta
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QPlainTextEdit, QSizePolicy)

from branding import notification_icon
from theme_tokens import get_theme
from ui_tokens import font_css


class ApprovalsPanel(QWidget):
    """Only a deliberate press may resolve the invocation visible at that press."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ApprovalsPage')
        self.setAccessibleName('AI permission requests')
        self.bridge = None
        self.current_id = None
        self._requests = []
        self._pressed = {}
        self._review_required = False
        self._title = ''
        self._context = ''
        self._theme = get_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.provider_icon = QLabel()
        self.provider_icon.setFixedSize(24, 24)
        self.heading = self._label('')
        self.heading.setObjectName('ApprovalHeading')
        self.heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.queue_text = self._label('')
        self.previous_button = self._button('', 'Previous permission request')
        self.next_button = self._button('', 'Next permission request')
        self.previous_button.setObjectName('ApprovalPrevious')
        self.next_button.setObjectName('ApprovalNext')
        self.previous_button.setFixedWidth(32)
        self.next_button.setFixedWidth(32)
        self.previous_button.clicked.connect(lambda: self._move(-1))
        self.next_button.clicked.connect(lambda: self._move(1))
        header.addWidget(self.provider_icon)
        header.addWidget(self.heading, 1)
        header.addWidget(self.queue_text)
        header.addWidget(self.previous_button)
        header.addWidget(self.next_button)
        root.addLayout(header)
        self.context = self._label('')
        self.context.setObjectName('ApprovalContext')
        self.context.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        root.addWidget(self.context)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(36)
        self.details.setAccessibleName('Exact requested tool arguments')
        self.details.setAccessibleDescription('Read-only JSON. Use arrow keys or the mouse wheel to inspect all arguments.')
        self.details.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.details, 1)
        self.empty_text = self._label('No pending requests')
        self.empty_text.setWordWrap(True)
        root.addWidget(self.empty_text, 1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.caption = self._label('')
        self.caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer.addWidget(self.caption, 1)
        self.deny_button = self._button('Deny', 'Deny this permission request')
        self.deny_button.setObjectName('ApprovalDeny')
        self.allow_button = self._button('Allow once', 'Allow this permission request once')
        self.allow_button.setObjectName('ApprovalAllow')
        for button, action in ((self.deny_button, 'deny'), (self.allow_button, 'allow')):
            button.pressed.connect(lambda value=action: self._capture(value))
            button.clicked.connect(lambda _, value=action: self._answer(value))
            footer.addWidget(button)
        root.addLayout(footer)
        self.set_theme(self._theme)
        self.review()

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        return label

    @staticmethod
    def _button(text, name):
        button = QPushButton(text)
        button.setFixedHeight(32)
        button.setToolTip(name)
        button.setAccessibleName(name)
        button.setIconSize(QSize(20, 20))
        return button

    def attach_bridge(self, bridge):
        if self.bridge is not None:
            self.bridge.changed.disconnect(self.review)
        self.bridge = bridge
        if bridge is not None:
            bridge.changed.connect(self.review)
        self.review()

    def review(self, request_id=None):
        records = self.bridge.pending() if self.bridge is not None else []
        self._requests = [record for record in records
                          if record['expires_at'] > time.monotonic()]
        ids = [record['id'] for record in self._requests]
        if isinstance(request_id, str) and request_id in ids:
            self._review_required = False
        desired = request_id if request_id in ids else self.current_id
        self.current_id = desired if desired in ids else (ids[0] if ids else None)
        active = self.current_id is not None
        for widget in (self.provider_icon, self.heading, self.queue_text,
                       self.context, self.details):
            widget.setVisible(active)
        self.empty_text.setVisible(not active)
        self.previous_button.setEnabled(active and len(ids) > 1)
        self.next_button.setEnabled(active and (len(ids) > 1 or self._review_required))
        self.allow_button.setEnabled(active and not self._review_required)
        self.deny_button.setEnabled(active and not self._review_required)
        if not active:
            self._title = self._context = ''
            error = getattr(self.bridge, 'error', '') if self.bridge is not None else ''
            self.empty_text.setText(str(error) if error else 'No pending requests')
            self.caption.setText('Codex needs hook trust · Claude Code only')
            self.caption.setToolTip('Review the Daisy hook in Codex /hooks. Supports Claude Code sessions.')
            self.details.clear()
            return
        index = ids.index(self.current_id)
        item = self._requests[index]
        provider = 'Codex' if item['provider'] == 'codex' else 'Claude'
        self.provider_icon.setPixmap(notification_icon(provider, self._theme['accent']).pixmap(24, 24))
        self.provider_icon.setAccessibleName(provider)
        self._title = f"{provider} · {self._safe(item['tool_name'])}"
        self._context = f"{self._safe(item['session_id'])} · {self._safe(item['cwd'])}"
        self.context.setToolTip(html.escape(self._context))
        self.context.setAccessibleDescription(self._context)
        self.queue_text.setText(f'{index + 1} / {len(ids)}')
        self.queue_text.setAccessibleName(f'Permission request {index + 1} of {len(ids)}')
        details = json.dumps(item['tool_input'], ensure_ascii=True, indent=2)
        if self.details.toPlainText() != details:
            self.details.setPlainText(details)
        self.caption.setText('Review next request →' if self._review_required
                             else 'Applies to this request only')
        self.caption.setToolTip('')
        self._elide()

    @staticmethod
    def _safe(value):
        return json.dumps(str(value), ensure_ascii=True)[1:-1]

    def _elide(self):
        for label, text in ((self.heading, self._title), (self.context, self._context)):
            label.setText(label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, label.width()))
            label.setAccessibleName(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _move(self, offset):
        ids = [record['id'] for record in self._requests]
        if self.current_id in ids:
            self.review(ids[(ids.index(self.current_id) + offset) % len(ids)])

    def _capture(self, action):
        self._pressed[action] = (self.bridge, self.current_id)

    def _answer(self, action):
        bridge, identifier = self._pressed.pop(action, (None, None))
        if bridge is self.bridge and bridge is not None and identifier is not None:
            # Resolve may synchronously publish the next item. Repeated clicks
            # and held keys must never authorize that newly displayed request.
            self._review_required = True
            bridge.resolve(identifier, action)
        self.review()

    def set_theme(self, theme):
        self._theme = theme
        self.previous_button.setIcon(qta.icon('ph.caret-left', color=theme['text']))
        self.next_button.setIcon(qta.icon('ph.caret-right', color=theme['text']))
        self.setStyleSheet(f'''
            QWidget#ApprovalsPage {{ color: {theme['text']}; background: transparent; {font_css('body')} }}
            QWidget#ApprovalsPage QLabel {{ color: {theme['text']}; background: transparent; {font_css('secondary')} }}
            QWidget#ApprovalsPage QLabel#ApprovalHeading {{ {font_css('title')} }}
            QWidget#ApprovalsPage QLabel#ApprovalContext {{ color: {theme['muted']}; {font_css('caption')} }}
            QWidget#ApprovalsPage QPlainTextEdit {{ color: {theme['text']}; background: {theme['surface']}; border: 1px solid transparent; border-radius: 8px; padding: 4px; {font_css('secondary')} }}
            QWidget#ApprovalsPage QPushButton {{ color: {theme['text']}; background: {theme['surface']}; border: 1px solid transparent; border-radius: 8px; padding: 0px 8px; min-height: 30px; max-height: 30px; }}
            QWidget#ApprovalsPage QPushButton#ApprovalPrevious, QWidget#ApprovalsPage QPushButton#ApprovalNext {{ padding: 0px; }}
            QWidget#ApprovalsPage QPushButton#ApprovalDeny {{ color: {theme['danger']}; }}
            QWidget#ApprovalsPage QPushButton#ApprovalAllow {{ color: {theme['accent']}; background: {theme['hover']}; }}
            QWidget#ApprovalsPage QPushButton:hover {{ background: {theme['hover']}; }}
            QWidget#ApprovalsPage QPushButton:pressed {{ background: {theme['border']}; }}
            QWidget#ApprovalsPage QPushButton:focus, QWidget#ApprovalsPage QPlainTextEdit:focus {{ border: 1px solid {theme['accent']}; }}
            QWidget#ApprovalsPage QPushButton:disabled {{ color: {theme['muted']}; background: transparent; }}
        ''')
        self.review()
