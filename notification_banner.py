"""The porcelain notification card's content: a light, macOS-style banner.

The card's body and shadow are painted by the window (notification_card.py);
this widget lays out the sender, title, message and actions on top. A permission
request adds Allow and Deny: they wake a moment after the card appears, answer
the one request shown, and can be pressed once.
"""
import json

from PyQt6.QtCore import Qt, QSize, QTimer, QVariantAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtWidgets import QWidget, QLabel, QToolButton, QHBoxLayout, QVBoxLayout
import qtawesome as qta
from media_widgets import ElidedLabel
from ui_tokens import SPACING, font_css
from theme_tokens import get_theme
from branding import notification_icon

CARD_W = 400
ICON_SIZE = 38
PAD = 14
ARM_MS = 700     # a click that was already on its way must not answer a request it never saw
RESULT_COLORS = {'allow': '#30d158', 'deny': '#ff453a'}
SUMMARY_KEYS = ('command', 'file_path', 'path', 'url', 'pattern', 'description')


def summarize(record, limit=90):
    """One plain line saying what is being asked: "Bash: npm test". Untrusted text, shown only."""
    tool = str(record.get('tool_name') or 'A tool')
    data = record.get('tool_input') if isinstance(record.get('tool_input'), dict) else {}
    detail = next((str(data[key]) for key in SUMMARY_KEYS if data.get(key)), '')
    if not detail and data:
        detail = json.dumps(data, ensure_ascii=False, default=str)
    text = ' '.join(f'{tool}: {detail}'.split()) if detail else tool
    return text if len(text) <= limit else text[:limit - 1] + '…'


class NotificationBanner(QWidget):
    dismissed = pyqtSignal()
    review_requested = pyqtSignal()
    approval_answered = pyqtSignal(str, str)   # request id, 'allow' or 'deny'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName('Notification')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._app_name = ''
        self._approval_id = None
        self._armed = False
        self._pop = None
        # Owned by the banner: a timer that outlives it would call into a deleted widget.
        self._arm_timer = QTimer(self)
        self._arm_timer.setSingleShot(True)
        self._arm_timer.timeout.connect(self._arm)
        root = QHBoxLayout(self)
        root.setContentsMargins(PAD, PAD - 2, PAD - 6, PAD)
        root.setSpacing(SPACING['inset'])
        self.icon = QLabel()
        self.icon.setFixedSize(ICON_SIZE, ICON_SIZE)
        root.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(1)
        header = QHBoxLayout()
        header.setSpacing(6)
        self.app = ElidedLabel()
        self.app.setObjectName('NotificationApp')
        self.when = QLabel('now')
        self.when.setObjectName('NotificationTime')
        self.dismiss = QToolButton()
        self.dismiss.setObjectName('NotificationDismiss')
        self.dismiss.setAccessibleName('Dismiss notification')
        self.dismiss.setToolTip('Dismiss notification')
        self.dismiss.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.dismiss.setFixedSize(32, 32)
        self.dismiss.setIconSize(QSize(12, 12))
        self.dismiss.clicked.connect(self.dismissed)
        header.addWidget(self.app, 1)
        header.addWidget(self.when, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.dismiss, 0, Qt.AlignmentFlag.AlignVCenter)
        column.addLayout(header)
        self.title = ElidedLabel()
        self.title.setObjectName('NotificationTitle')
        column.addWidget(self.title)
        body = QHBoxLayout()
        body.setSpacing(SPACING['control'])
        self.message = ElidedLabel()
        self.message.setObjectName('NotificationMessage')
        body.addWidget(self.message, 1)
        self.review = QToolButton()
        self.review.setObjectName('NotificationReview')
        self.review.setText('Review')
        self.review.setAccessibleName('Review pending permission requests')
        self.review.setToolTip('Open Tools → Approvals')
        self.review.setFixedSize(72, 32)
        self.review.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.review.clicked.connect(self.review_requested)
        self.review.hide()
        body.addWidget(self.review, 0, Qt.AlignmentFlag.AlignVCenter)
        column.addLayout(body)
        self.actions = QWidget()
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setSpacing(SPACING['control'])
        actions.addStretch()
        self.details = self._action('NotificationReview', 'Details', 'Inspect the full request in Tools → Approvals', 76)
        self.deny = self._action('NotificationReview', 'Deny', 'Deny this request', 68)
        self.allow = self._action('NotificationAllow', 'Allow', 'Allow this request once', 68)
        self.details.clicked.connect(self.review_requested)
        self.deny.clicked.connect(lambda: self._answer('deny'))
        self.allow.clicked.connect(lambda: self._answer('allow'))
        for button in (self.details, self.deny, self.allow):
            actions.addWidget(button)
        self.actions.hide()
        column.addWidget(self.actions)
        root.addLayout(column, 1)
        self.set_theme(get_theme())

    def set_message(self, app, title, message):
        self._app_name = str(app or '')
        self._refresh_icon()
        self.app.setText(str(app or 'Notification'))
        self.title.setText(str(title or message or 'Notification'))
        self.message.setText(str(message if title else ''))
        self.message.setVisible(bool(title and message))
        self.setAccessibleDescription('\n'.join(str(v) for v in (app, title, message) if v))

    def set_review_available(self, available):
        self.review.setVisible(bool(available) and self._approval_id is None)

    def _action(self, name, text, tip, width):
        button = QToolButton()
        button.setObjectName(name)
        button.setText(text)
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.setFixedSize(width, 32)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return button

    # -- a permission request -------------------------------------------------
    def set_approval(self, record):
        """Show Allow and Deny for this request, or hide them for None."""
        request_id = record['id'] if record else None
        if request_id == self._approval_id:
            return
        self._approval_id = request_id
        self._armed = False
        self._arm_timer.stop()
        self.actions.setVisible(bool(record))
        self.review.hide() if record else None
        for button in (self.allow, self.deny):
            button.setEnabled(False)
        if record:
            self.set_message(self._app_name or 'Permission', 'Permission requested', summarize(record))
            self._arm_timer.start(ARM_MS)

    def _arm(self):
        if self._approval_id is not None:
            self._armed = True
            for button in (self.allow, self.deny):
                button.setEnabled(True)

    def _answer(self, decision):
        request_id = self._approval_id
        if request_id is None or not self._armed:
            return
        self._armed = False
        for button in (self.allow, self.deny):
            button.setEnabled(False)
        self.approval_answered.emit(request_id, decision)

    def show_result(self, decision):
        """The answer went out: a check or a cross pops in, and the actions go away."""
        self._approval_id = None
        self.actions.hide()
        allowed = decision == 'allow'
        self.app.setText(self._app_name or 'Permission')
        self.title.setText('Allowed' if allowed else 'Denied')
        self.message.setText('Daisy told it to go ahead.' if allowed else 'Daisy told it to stop here.')
        self.message.show()
        color = RESULT_COLORS['allow' if allowed else 'deny']
        name = 'ph.check-circle-fill' if allowed else 'ph.x-circle-fill'
        pop = QVariantAnimation(self)
        pop.setDuration(320)
        pop.setStartValue(0.)
        pop.setEndValue(1.)
        pop.setEasingCurve(QEasingCurve.Type.OutBack)
        pop.valueChanged.connect(lambda p: self.icon.setPixmap(
            qta.icon(name, color=color).pixmap(max(8, round(ICON_SIZE * (.5 + .5 * p))), max(8, round(ICON_SIZE * (.5 + .5 * p))))))
        self._pop = pop
        pop.start()

    def card_height(self):
        """The card's height at its fixed width, from what it shows."""
        self.layout().activate()
        return max(self.layout().sizeHint().height(), ICON_SIZE + 2 * PAD)

    def set_theme(self, theme):
        # The card is porcelain whatever the island's theme; labels use Apple's
        # light-mode label, secondary and tertiary greys.
        self._theme = theme
        self._refresh_icon()
        self.dismiss.setIcon(qta.icon('ph.x-bold', color=theme['porcelain_tertiary']))
        self.setStyleSheet(f'''
            QWidget {{ background: transparent; color: {theme['porcelain_label']}; }}
            QLabel {{ {font_css('body')} border: none; }}
            QLabel#NotificationApp, QLabel#NotificationTime {{ {font_css('caption')} color: {theme['porcelain_tertiary']}; }}
            QLabel#NotificationTitle {{ {font_css('title')} color: {theme['porcelain_label']}; }}
            QLabel#NotificationMessage {{ {font_css('body')} color: {theme['porcelain_secondary']}; }}
            QToolButton#NotificationDismiss {{ border: none; border-radius: 16px; background: transparent; }}
            QToolButton#NotificationDismiss:hover {{ background: {theme['porcelain_fill']}; }}
            QToolButton#NotificationDismiss:focus {{ border: 1px solid {theme['accent']}; }}
            QToolButton#NotificationReview {{ {font_css('title')} color: {theme['porcelain_label']};
                background: {theme['porcelain_fill']}; border: none; border-radius: 16px; }}
            QToolButton#NotificationReview:hover {{ background: {theme['porcelain_fill_hover']}; }}
            QToolButton#NotificationReview:focus {{ border: 1px solid {theme['accent']}; }}
            QToolButton#NotificationReview:disabled {{ color: {theme['porcelain_tertiary']}; }}
            QToolButton#NotificationAllow {{ {font_css('title')} color: #ffffff; background: {theme['porcelain_label']};
                border: none; border-radius: 16px; }}
            QToolButton#NotificationAllow:hover {{ background: #3a3a3c; }}
            QToolButton#NotificationAllow:focus {{ border: 2px solid {theme['accent']}; }}
            QToolButton#NotificationAllow:disabled {{ background: {theme['porcelain_fill']}; color: {theme['porcelain_tertiary']}; }}
        ''')

    def _refresh_icon(self):
        self.icon.setPixmap(notification_icon(self._app_name, self._theme['porcelain_secondary'])
                            .pixmap(ICON_SIZE, ICON_SIZE))
        self.icon.setAccessibleName((self._app_name or 'Notification') + ' icon')
