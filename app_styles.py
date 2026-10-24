"""Shared Qt styling: every surface uses the selected Daisy tokens."""
from theme_tokens import get_theme
from ui_tokens import font_css


def get_stylesheet(theme=None):
    t = theme or get_theme()
    return f'''
    QWidget#IslandWidget, QWidget#IslandRoot {{ background: transparent; border: none; }}
    QLabel {{ color: {t['text']}; {font_css('body')} }}
    QLabel#TitleLabel {{ {font_css('title')} }}
    QLabel#SubtitleLabel, QLabel#PerfLabel {{ {font_css('secondary')} color: {t['muted']}; }}
    QPushButton {{ {font_css('body')} color: {t['text']}; background: {t['surface']}; border: 1px solid transparent; border-radius: 8px; padding: 6px 12px; min-height: 18px; }}
    QPushButton:hover {{ background: {t['hover']}; }}
    QPushButton:pressed {{ background: {t['border']}; }}
    QPushButton:focus {{ border: 1px solid {t['accent']}; }}
    QPushButton:disabled {{ color: {t['muted']}; background: {t['surface']}; }}
    QPushButton#MediaButton {{ border: none; border-radius: 14px; width: 28px; height: 28px; padding: 2px; }}
    QToolButton {{ color: {t['muted']}; background: transparent; border: 1px solid transparent; border-radius: 10px; padding: 0; {font_css('caption')} }}
    QToolButton:hover {{ background: {t['hover']}; color: {t['text']}; }}
    QToolButton:checked {{ background: transparent; color: {t['text']}; }}
    QToolButton#PowerButton {{ border-radius: 16px; }}
    QToolButton#PowerButton:hover {{ background: {t['surface']}; }}
    QToolButton#PowerButton::menu-indicator {{ image: none; width: 0; }}
    QToolButton:pressed {{ background: {t['border']}; }}
    QToolButton:focus {{ border-color: {t['accent']}; }}
    QMenu {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 6px; }}
    QMenu::item {{ padding: 6px 20px; }}
    QMenu::item:selected {{ background: {t['hover']}; }}
    QMessageBox {{ background: {t['background']}; }}
    QLineEdit, QComboBox {{ color: {t['text']}; background: {t['surface']}; border: 1px solid {t['control_border']}; border-radius: 8px; padding: 10px; }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {t['accent']}; }}
    QListWidget {{ color: {t['text']}; background: transparent; border: none; }}
    QListWidget::item {{ background: {t['surface']}; border-radius: 8px; padding: 10px; margin-bottom: 5px; }}
    QListWidget::item:selected {{ border: 1px solid {t['accent']}; }}
    QPushButton#DangerAction {{ color: {t['danger']}; }}
    QPushButton#PrimaryAction {{ background: {t['accent']}; color: {t['background']}; padding: 12px; font-weight: bold; }}
    QProgressBar {{ background: {t['hover']}; border: none; border-radius: 2px; }}
    QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
    QScrollBar:vertical {{ background: transparent; width: 0px; margin: 0; border: none; }}
    QScrollBar:horizontal {{ background: transparent; height: 0px; margin: 0; border: none; }}
    QScrollBar::handle:vertical {{ background: {t['control_border']}; border-radius: 4px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; background: transparent; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    '''
