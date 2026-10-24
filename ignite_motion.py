"""Ignite: Daisy's spring-driven shell motion, one-shot rim light and blur-in reveal.

The timing functions are plain math so they can be tested without a window.
Text and artwork never scale: content only fades, sharpens and rises 10 px.
"""
import math

from PyQt6.QtCore import QPointF, QVariantAnimation, Qt
from PyQt6.QtGui import QBrush, QColor, QConicalGradient, QPen, QRadialGradient

# Damped springs with unit mass: (stiffness, damping) per axis. Height lags width,
# so the island stretches sideways before it drops. Opening overshoots about 9%.
OPEN = dict(w=(420., 25.), h=(300., 19.), lag=35, squash=0, settle=620)
SQUASH_OPEN = dict(OPEN, squash=90)
CLOSE = dict(w=(520., 30.), h=(520., 26.), lag=0, squash=0, settle=420)
SQUASH_PX = (14, 4)
REVEAL_DELAY = 190
REVEAL_MS = 460
RISE_PX = 10
RIM_DELAY = 150
RIM_MS = 1150


def spring(t, stiffness, damping):
    """Unit step response of a damped spring after t seconds: 0, then settles at 1."""
    if t <= 0:
        return 0.
    omega = math.sqrt(stiffness)
    zeta = damping / (2 * omega)
    if zeta >= 1:
        return 1 - math.exp(-omega * t) * (1 + omega * t)
    damped = omega * math.sqrt(1 - zeta * zeta)
    return 1 - math.exp(-zeta * omega * t) * (
        math.cos(damped * t) + zeta * omega / damped * math.sin(damped * t))


def _in_out(p):
    return 2 * p * p if p < .5 else 1 - (-2 * p + 2) ** 2 / 2


def total_ms(profile):
    return profile['squash'] + profile['settle']


def shell_size(start, end, ms, profile):
    """Island (width, height) `ms` into a transition; exactly `end` once settled."""
    if ms >= total_ms(profile):
        return end
    (w0, h0), (w1, h1) = start, end
    squash = profile['squash']
    if squash:
        if ms < squash:
            e = _in_out(ms / squash)
            return w0 - SQUASH_PX[0] * e, h0 - SQUASH_PX[1] * e
        w0, h0, ms = w0 - SQUASH_PX[0], h0 - SQUASH_PX[1], ms - squash
    width = w0 + (w1 - w0) * spring(ms / 1000, *profile['w'])
    height = h0 + (h1 - h0) * spring(max(0, ms - profile['lag']) / 1000, *profile['h'])
    return width, height


def reveal_ease(p):
    return 1 - (1 - p) ** 3


def rim_alpha(p):
    """The light fades in, holds for most of its turn, then lets go."""
    if p <= 0 or p >= 1:
        return 0.
    if p < .12:
        return p / .12
    if p > .7:
        return (1 - p) / .3
    return 1.


def rim_angle(p):
    """Head of the light in Qt degrees: from just left of 12 o'clock, one clockwise turn."""
    return 120. - 360. * _in_out(min(1., max(0., p)))


# -- Qt wiring -----------------------------------------------------------------
def install(window):
    window.ignite_phase = 0.


def apply_reveal(window, p):
    """p = 0: content hidden, soft and 10 px low. p = 1: settled and sharp."""
    window.content_layer.set_reveal(p, round(RISE_PX * (1 - p)), p)


def set_rim(window, p):
    window.ignite_phase = p
    window.update_island_region()


def settle(window):
    """Clear the rim light; the content layer is settled by the shell."""
    if window.ignite_phase:
        set_rim(window, 0.)


def _clock(duration, on_value):
    clock = QVariantAnimation()
    clock.setStartValue(0.)
    clock.setEndValue(1.)
    clock.setDuration(duration)
    clock.valueChanged.connect(on_value)
    return clock


def size_animation(window, start, end, profile):
    """One linear clock drives both axes, so they start and finish together."""
    total = total_ms(profile)

    def step(p):
        width, height = shell_size(start, end, p * total, profile)
        # The overshoot never leaves the window, which is already clamped to the screen.
        width = min(round(width), window.width())
        height = min(round(height), window.height() - int(window.get_island_rect().top()))
        window.set_island_size(width, height)
    return _clock(total, step)


def reveal_animation(window):
    return _clock(REVEAL_MS, lambda p: apply_reveal(window, reveal_ease(p)))


def rim_animation(window):
    return _clock(RIM_MS, lambda p: set_rim(window, p))


def paint_rim(painter, rect, shape, edge, phase, color):
    """A bloom from the top edge, a soft aura, and one light running round the edge."""
    alpha = rim_alpha(phase)
    if alpha <= 0:
        return
    tint = QColor(color)
    painter.save()
    painter.setClipPath(shape)
    bloom = QRadialGradient(QPointF(rect.center().x(), rect.top()), max(rect.width() * .6, rect.height()))
    for stop, strength in ((0., .32), (1., 0.)):
        shade = QColor(tint)
        shade.setAlphaF(strength * alpha)
        bloom.setColorAt(stop, shade)
    painter.fillPath(shape, QBrush(bloom))
    painter.setClipping(False)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for width, strength in ((16., .08), (8., .14)):
        shade = QColor(tint)
        shade.setAlphaF(strength * alpha)
        painter.setPen(QPen(shade, width))
        painter.drawPath(edge)
    light = QConicalGradient(QPointF(rect.center()), rim_angle(phase))
    head = tint.lighter(140)
    for stop, source, strength in ((0., head, 1.), (.06, tint, .9), (.28, tint, 0.), (.95, tint, 0.), (1., head, 1.)):
        shade = QColor(source)
        shade.setAlphaF(strength * alpha)
        light.setColorAt(stop, shade)
    painter.setPen(QPen(QBrush(light), 2.2))
    painter.drawPath(edge)
    painter.restore()
