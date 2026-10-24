"""Daisy identity and resources, shared by source and frozen builds."""
from pathlib import Path
from functools import lru_cache
import os
import sys

from PyQt6.QtGui import QIcon, QFont, QFontDatabase
import qtawesome as qta

APP_NAME = "Daisy"
_font_ids = []


def resource_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / name)


def app_icon():
    return QIcon(resource_path("assets/daisy.ico"))


def notification_icon(app_name, fallback_color):
    """Use unchanged installed-publisher artwork based on sender, never message text."""
    sender = str(app_name or '').strip().casefold()
    if sender in ('codex', 'chatgpt', 'openai.codex') or sender.startswith('openai.codex_'):
        name = 'codex'
    elif sender in ('claude', 'claude code', 'anthropic.claude') or sender.startswith('claude_'):
        name = 'claude'
    else:
        name = None
    if name is not None:
        icon = QIcon(resource_path(f'assets/notification-icons/{name}.png'))
        if not icon.isNull():
            return icon
    return qta.icon('ph.bell-simple', color=fallback_color)


def configure_fonts(app):
    """Register the real Windows UI font even when Qt's font enumeration fails."""
    if not _font_ids:
        inter = Path(resource_path('assets/fonts/InterVariable.ttf'))
        if inter.is_file():
            font_id = QFontDatabase.addApplicationFont(str(inter))
            if font_id >= 0:
                _font_ids.append(font_id)
        fonts = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
        for name in ('SegUIVar.ttf', 'segoeui.ttf', 'seguisb.ttf', 'segoeuib.ttf', 'consola.ttf'):
            path = fonts / name
            if path.is_file():
                font_id = QFontDatabase.addApplicationFont(str(path))
                if font_id >= 0:
                    _font_ids.append(font_id)
    from ui_tokens import font
    app.setFont(font('body'))


def media_identity(source='', title=''):
    source, title = str(source or '').lower(), str(title or '').lower()
    if 'spotify' in source:
        return 'Spotify', 'spotify'
    if 'netflix' in source:
        return 'Netflix', 'netflix'
    if 'youtube' in source:
        return 'YouTube', 'youtube'
    if 'netflix' in title:
        return 'Netflix', 'netflix'
    if 'youtube' in title:
        return 'YouTube', 'youtube'
    if any(name in source for name in ('chrome', 'edge', 'firefox', 'browser', 'brave', 'opera')):
        return 'Browser', 'browser'
    return 'Media', 'media'


def media_icon(source='', title='', size=32):
    """Load untouched publisher assets; no network access or redrawn brands."""
    kind = media_identity(source, title)[1]
    if kind == 'browser':
        raw_source = str(source or '').lower()
        if 'chrome' in raw_source:
            kind = 'chrome'
        elif 'edge' in raw_source:
            kind = 'edge'
        elif 'brave' in raw_source:
            kind = 'brave'
    return _brand_icon(kind, max(16, min(int(size), 128)))


@lru_cache(maxsize=32)
def _brand_icon(kind, size):
    files = {'spotify': 'spotify.svg', 'netflix': 'netflix.png',
             'youtube': 'youtube.png', 'chrome': 'chrome.png', 'edge': 'edge.png',
             'brave': 'brave.png'}
    if kind in files:
        icon = QIcon(resource_path('assets/provider-icons/' + files[kind]))
        if not icon.isNull():
            return icon
    # Unknown sessions remain generic, rather than impersonating a publisher.
    return qta.icon('ph.globe' if kind == 'browser' else 'ph.music-notes', color='white')
