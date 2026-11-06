"""The light each open-island page brings with it, painted behind its content.

Now glows in the album's colour (or the accent), Weather in sky and sun, Tasks in
a faint accent, Calendar in night blue and Tools in amber. Changing page
crossfades the two washes; reduced motion switches at once.
"""
from PyQt6.QtCore import QPointF, QVariantAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QRadialGradient

FADE_MS = 320


def _companion(color):
    hue, saturation, value, _ = QColor(color).getHsvF()
    hue = .72 if hue < 0 else hue
    return QColor.fromHsvF((hue + .08) % 1., max(saturation, .5), max(value, .85))


def spots(window, page):
    """(colour, x, y, radius as a share of width, strength) for each light."""
    t = window.theme
    if page == 'dashboard':
        tint = window.ambient_tint()
        return ((QColor(tint), .2, .45, .42, .5), (_companion(tint), .34, .82, .3, .3))
    if page == 'weather':
        return ((QColor(t['wash_sky']), .15, .2, .6, .55), (QColor(t['wash_sun']), .22, .18, .2, .38))
    if page == 'calendar':
        return ((QColor(t['accent']), .1, .3, .5, .18),)
    if page == 'month':
        return ((QColor(t['wash_night']), .12, .5, .55, .9),)
    if page == 'tools':
        return ((QColor(t['timer_accent']), .18, .5, .45, .2),)
    return ()


def set_page(window, page):
    current = getattr(window, '_wash_page', None)
    if page == current:
        return
    window._wash_from, window._wash_page = current, page
    animation = getattr(window, '_wash_animation', None)
    if animation is None:
        animation = QVariantAnimation(window)
        animation.setStartValue(0.)
        animation.setEndValue(1.)
        animation.setDuration(FADE_MS)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def step(value):
            window._wash_mix = value
            window.update_island_region()
        animation.valueChanged.connect(step)
        window._wash_animation = animation
    animation.stop()
    if getattr(window, 'reduced_motion', False):
        window._wash_mix = 1.
        window.update_island_region()
        return
    window._wash_mix = 0.
    animation.start()


def paint(window, painter, rect):
    mix = getattr(window, '_wash_mix', 1.)
    for page, weight in ((getattr(window, '_wash_from', None), 1. - mix), (getattr(window, '_wash_page', None), mix)):
        if not page or weight <= 0.:
            continue
        for color, x, y, radius, strength in spots(window, page):
            centre = QPointF(rect.x() + rect.width() * x, rect.y() + rect.height() * y)
            glow = QRadialGradient(centre, rect.width() * radius)
            inner, outer = QColor(color), QColor(color)
            inner.setAlphaF(min(1., strength * weight))
            outer.setAlphaF(0.)
            glow.setColorAt(0., inner)
            glow.setColorAt(1., outer)
            painter.fillRect(rect, glow)
