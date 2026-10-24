"""Native Settings with a detached live preview and explicit transactional Apply."""
from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QListWidget, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from app_styles import get_stylesheet
from settings_draft import create_draft, validate_draft
from settings_pages import SettingsPages
from settings_preview import SettingsPreview
from settings_rules_page import RulesPage
from theme_tokens import get_theme
from ui_tokens import font, font_css
from hover_feedback import install_hover_feedback
from motion_policy import effective_reduced_motion


class SettingsDialog(QDialog):
    def __init__(self, settings, apply_callback, diagnostics=None, parent=None,
                 actions=None, media_sources=None):
        super().__init__(parent)
        self.setWindowTitle('Daisy Settings')
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = max(320, available.width() - 32) if available else 900
        height = max(320, available.height() - 40) if available else 760
        self._compact_layout = height < 620
        self.setMinimumSize(min(680, width), min(540, height))
        self.setMaximumHeight(height)
        self.resize(min(900, width), min(760, height))
        self.draft = create_draft(settings)
        self.setFont(font('body'))
        self._apply_callback = apply_callback
        self.controls = {}
        outer = QVBoxLayout(self)
        margin = 12 if self._compact_layout else 24
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(8 if self._compact_layout else 16)
        heading = QLabel('Settings')
        heading.setObjectName('SettingsHeading')
        heading.setVisible(not self._compact_layout)
        outer.addWidget(heading)
        preview_row = QHBoxLayout()
        label = QLabel('Live preview')
        preview_row.addWidget(label)
        preview_row.addStretch()
        self.preview_view = QComboBox()
        self.preview_view.addItems(['Compact', 'Expanded', 'Edge line'])
        self.preview_view.setAccessibleName('Preview state')
        preview_row.addWidget(self.preview_view)
        outer.addLayout(preview_row)
        self.preview = SettingsPreview(self.draft)
        if self._compact_layout:
            self.preview.setMinimumHeight(100)
        self.preview_view.currentTextChanged.connect(self.preview.set_view)
        outer.addWidget(self.preview)
        content = QHBoxLayout()
        self.navigation = QListWidget()
        self.navigation.setAccessibleName('Settings sections')
        self.navigation.addItems(['Appearance', 'App rules', 'Media', 'Tools', 'General'])
        self.navigation.setFixedWidth(136)
        content.addWidget(self.navigation)
        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        outer.addLayout(content, 1)
        pages = SettingsPages(self.draft, self._change, self.controls, actions,
                              diagnostics, media_sources)
        self.rules_page = RulesPage(self.draft['app_rules'], lambda value: self._change('app_rules', value))
        for page in (pages.appearance(), self.rules_page, pages.media(), pages.tools(), pages.general()):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        self.action_buttons = pages.action_buttons
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setAccessibleName('Settings save status')
        self.error_label.setObjectName('SettingsError')
        outer.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_changes)
        self.buttons.accepted.connect(self._accept_changes)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)
        self._set_theme()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'buttons'):
            return
        compact = self.height() < 620
        changed = compact != self._compact_layout
        self._compact_layout = compact
        margin = 12 if compact else 24
        self.layout().setContentsMargins(margin, margin, margin, margin)
        self.layout().setSpacing(8 if compact else 16)
        self.findChild(QLabel, 'SettingsHeading').setVisible(not compact)
        self.preview.setFixedHeight(100 if compact else 150)
        if changed:
            self._set_theme()

    def _change(self, key, value):
        self.draft[key] = value
        self.error_label.clear()
        self.preview.set_settings(self.draft)
        if key in ('theme', 'surface_treatment', 'motion_mode'):
            self._set_theme()

    def _set_theme(self):
        theme = get_theme(self.draft['theme'], self.draft['surface_treatment'])
        self.setStyleSheet(get_stylesheet(theme=theme) + f'''
            QDialog, QScrollArea, QStackedWidget, QScrollArea > QWidget > QWidget {{
                background: {theme['background']}; color: {theme['text']};
                {font_css('body')}
            }}
            QLabel#SettingsHeading {{ {font_css('section')} }}
            QLabel#SettingsDescription {{ {font_css('secondary')} color: {theme['muted']}; padding-bottom: 16px; }}
            QLabel#SettingsError {{ color: {theme['accent']}; }}
            QCheckBox, QSpinBox, QTableWidget, QHeaderView::section {{
                color: {theme['text']}; background: {theme['surface']};
                border: 1px solid {theme['control_border']}; padding: 6px;
            }}
            QComboBox QAbstractItemView {{ color: {theme['text']}; background: {theme['surface']};
                selection-background-color: {theme['hover']}; }}
            QComboBox, QPushButton, QLineEdit, QSpinBox {{ min-height: 32px; }}
            QCheckBox {{ min-height: 32px; }}
            QSpinBox:focus, QCheckBox:focus, QTableWidget:focus {{ border-color: {theme['accent']}; }}
            QTableWidget::item:selected {{ background: {theme['hover']}; color: {theme['text']}; }}
            QListWidget::item:selected {{ background: {theme['hover']}; color: {theme['text']}; }}
            QTableWidget {{ gridline-color: {theme['border']}; }}
            QScrollBar:vertical {{ background: transparent; width: 0px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {theme['border']}; min-height: 24px; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: {theme['muted']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QCheckBox {{ border: none; background: transparent; }}
            QCheckBox::indicator {{ width: 15px; height: 15px; background: {theme['surface']};
                border: 1px solid {theme['muted']}; border-radius: 3px; }}
            QCheckBox::indicator:checked {{ background: {theme['accent']}; border-color: {theme['accent']}; }}
        ''')
        if self._compact_layout:
            self.setStyleSheet(self.styleSheet() + '''
                QComboBox, QPushButton, QLineEdit, QSpinBox { min-height: 24px; padding: 4px; }
                QLabel#SettingsDescription { padding-bottom: 8px; }
                QListWidget::item { padding: 4px; margin-bottom: 0; }
            ''')
        install_hover_feedback(self, theme['hover'],
                               effective_reduced_motion(self.draft['motion_mode']))

    def apply_changes(self):
        try:
            validate_draft(self.draft)
            success, message = self._apply_callback(deepcopy(self.draft))
            if not success:
                self.error_label.setText(str(message or 'Daisy could not save these changes. Try again.'))
                return False
        except (ValueError, OSError, RuntimeError, TypeError) as exc:
            self.error_label.setText(str(exc) or 'Daisy could not save these changes.')
            return False
        self.error_label.setText('Saved.')
        return True

    def _accept_changes(self):
        if self.apply_changes():
            self.accept()

