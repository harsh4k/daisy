"""The porcelain notification card's content: a light, macOS-style banner.

The card's body and shadow are painted by the window (notification_card.py);
this widget only lays out the sender, title, message and actions on top.
No approval or inbox behaviour is implied.
"""
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QWidget, QLabel, QToolButton, QHBoxLayout, QVBoxLayout
import qtawesome as qta
from media_widgets import ElidedLabel
from ui_tokens import SPACING, font_css
from theme_tokens import get_theme
from branding import notification_icon

CARD_W = 400
ICON_SIZE = 38
PAD = 14


class NotificationBanner(QWidget):
    dismissed = pyqtSignal()
    review_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName('Notification')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._app_name = ''
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
        self.review.setVisible(bool(available))

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
        ''')

    def _refresh_icon(self):
        self.icon.setPixmap(notification_icon(self._app_name, self._theme['porcelain_secondary'])
                            .pixmap(ICON_SIZE, ICON_SIZE))
        self.icon.setAccessibleName((self._app_name or 'Notification') + ' icon')
