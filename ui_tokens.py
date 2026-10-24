"""Shared native typography, spacing and motion roles for Daisy."""
from PyQt6.QtGui import QFont, QFontDatabase, QFontMetrics

FAMILY = 'Inter Variable'
# macOS layout rhythm on a 4 px grid: 20 px edge insets, 16 between groups,
# 12 inside cards, 8 between controls, 4 between related lines of text.
SPACING = dict(outer=20, group=16, inset=12, control=8, text=4)
# Corner radii. Nested shapes stay concentric: inner = outer - inset.
RADIUS = dict(panel=28, card=20, inner=12, control=8, small=6)
MOTION = dict(open=260, close=200, close_fade=80, reveal=120,
              page_out=60, page_in=100, hover=100, edge=220)
# macOS text styles mapped onto Inter: Title 2 17, Headline 13 semibold, Body 13,
# Callout 12, Footnote 11. The large timer keeps its 32 px display role.
_ROLES = dict(display=(32, 600), section=(17, 600), title=(13, 600),
              body=(13, 400), secondary=(12, 400), time=(11, 400),
              compact=(13, 600), caption=(11, 400), metric=(12, 400))
# Apple tightens larger text; Inter needs the same to read like SF at size.
_TRACKING = {32: -.6, 17: -.25}
NUMERIC = ('time', 'compact', 'display', 'metric')


def concentric(outer, inset):
    """Radius for a shape inset inside another so both curves share a centre."""
    return max(0, outer - inset)


def resolved_family():
    """Use bundled Inter, with the existing Windows UI fonts as fallbacks."""
    available = QFontDatabase.families()
    return next((name for name in (FAMILY, 'Inter', 'Segoe UI Variable', 'Segoe UI')
                 if name in available), 'Segoe UI')


def stable_digits(font):
    """Report whether every digit shares one advance width in this font."""
    metrics = QFontMetrics(font)
    widths = [metrics.horizontalAdvance(str(digit) * 4) for digit in range(10)]
    return max(widths) - min(widths) <= 1


def numeric_font(size, weight):
    """Return a numeric font whose digits never shift while the clock runs."""
    result = QFont(resolved_family())
    result.setPixelSize(size)
    result.setWeight(QFont.Weight(weight))
    if hasattr(result, 'setFeature'):
        result.setFeature(QFont.Tag.fromString('tnum'), 1)
    if not stable_digits(result):
        result.setFamily('Consolas')
        result.setStyleHint(QFont.StyleHint.Monospace)
    return result


def font(role='body'):
    """Return pixel-based roles, with verified tabular numerical rendering."""
    size, weight = _ROLES[role]
    result = numeric_font(size, weight) if role in NUMERIC else QFont(resolved_family())
    if role not in NUMERIC:
        result.setPixelSize(size)
        result.setWeight(QFont.Weight(weight))
    if size in _TRACKING:
        result.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, _TRACKING[size])
    return result


def font_css(role='body'):
    """Return the stylesheet form of a role, using the verified numeric family."""
    size, weight = _ROLES[role]
    family = font(role).family() if role in NUMERIC else resolved_family()
    return f'font-family: "{family}"; font-size: {size}px; font-weight: {weight};'


def tag_role(widget, role='body', muted=False, accent=False):
    """Record a semantic role so panels restyle from tokens, never literal CSS."""
    widget.setProperty('daisyTypeRole', role)
    widget.setProperty('daisyMuted', bool(muted))
    widget.setProperty('daisyAccent', bool(accent))
    widget.setStyleSheet('')
    return widget


role_style = font_css
