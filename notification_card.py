"""The porcelain card that drops from the island when a notification arrives.

The window paints the card's shadow and porcelain body; the live banner sits on
top at rest. While the card drops in or lifts away, one snapshot of the banner
is drawn instead, so motion never re-lays out or re-renders live widgets.
"""
from PyQt6.QtCore import QPointF, QRectF, Qt, QVariantAnimation, QEasingCurve, QSequentialAnimationGroup, QPauseAnimation
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

import ignite_motion as ignite
import overlay_fit
from notification_banner import CARD_W
from ui_tokens import RADIUS

GAP = 8              # between the island and the card
DROP = 22            # the card starts this far up, tucked under the island
SHADOW = 28          # room around the card for its shadow
PRESENT_DELAY = 120  # the island swells first, then the card drops
PRESENT_MS = 560
SPRING = (300., 21.)  # a gentle drop that dips ~2 px past rest, then settles
RETRACT_MS = 200


def _soft(image, factor):
    small = image.scaled(max(1, image.width() // factor), max(1, image.height() // factor),
                         Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return small.scaled(image.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


class CardMotion:
    def __init__(self, window, banner):
        self.window, self.banner = window, banner
        self.progress = 0.   # 0: tucked away and invisible; 1: resting below the island
        self.wanted = False  # a notification with content belongs on screen
        self.pixmap = None   # the banner's snapshot while the card moves
        self.height = 0
        self._shadow = None
        self._shadow_key = None
        banner.hide()

    # -- geometry ---------------------------------------------------------------
    def width(self):
        return min(CARD_W, self.window.screen().availableGeometry().width() - 32)

    def rest_rect(self):
        window = self.window
        top = overlay_fit.island_top(window) + window.NOTIFY_H + GAP
        width = self.width()
        return QRectF(round(window.width() / 2 - width / 2), top, width, self.height or self.banner.card_height())

    def rect(self):
        rect = self.rest_rect()
        rect.translate(0, -(1. - self.progress) * DROP)
        return rect

    def present_on_screen(self):
        return self.wanted or self.progress > 0.

    def extent(self):
        """Room the overlay keeps below the island for the card and its shadow."""
        return int(round(GAP + self.rest_rect().height() + SHADOW)) if self.present_on_screen() else 0

    def min_width(self):
        return self.width() + 2 * SHADOW if self.present_on_screen() else 0

    def layout(self):
        """Size and place the live banner at the card's resting position."""
        self.banner.setFixedWidth(self.width())
        self.height = self.banner.card_height()
        self.banner.setFixedHeight(self.height)
        self.banner.move(self.rest_rect().toAlignedRect().topLeft())

    def dirty(self):
        return self.rest_rect().adjusted(-SHADOW, -DROP - SHADOW, SHADOW, SHADOW).toAlignedRect()

    def set_progress(self, value):
        self.progress = value
        self.window.update(self.dirty())

    # -- snapshot lifecycle -----------------------------------------------------
    def capture(self):
        self.layout()
        self.pixmap = self.banner.grab()
        self.banner.hide()
        self.window.update(self.dirty())

    def settle(self):
        """End any motion: rest fully shown or fully away, with live widgets."""
        self.pixmap = None
        self.progress = 1. if self.wanted else 0.
        if self.wanted:
            self.layout()
            self.banner.show()
            self.banner.raise_()
        else:
            self.banner.hide()
        self.window.update(self.dirty())

    # -- motion -----------------------------------------------------------------
    def present(self):
        """Drop the card in; an animation for the shell's motion group."""
        self.wanted = True
        sequence = QSequentialAnimationGroup()
        pause = QPauseAnimation(PRESENT_DELAY)
        # The banner is pictured only now, after the island has applied its content.
        pause.finished.connect(self.capture)
        sequence.addAnimation(pause)
        clock = QVariantAnimation()
        clock.setStartValue(0.)
        clock.setEndValue(1.)
        clock.setDuration(PRESENT_MS)
        clock.valueChanged.connect(lambda t: self.set_progress(1. if t >= 1. else ignite.spring(t * PRESENT_MS / 1000, *SPRING)))
        clock.finished.connect(self.settle)
        sequence.addAnimation(clock)
        return sequence

    def retract(self):
        """Lift the card away under the island; None when nothing is showing."""
        self.wanted = False
        if self.progress <= 0.:
            self.settle()
            return None
        start = self.progress
        self.capture()
        clock = QVariantAnimation()
        clock.setStartValue(start)
        clock.setEndValue(0.)
        clock.setDuration(RETRACT_MS)
        clock.setEasingCurve(QEasingCurve.Type.InCubic)
        clock.valueChanged.connect(self.set_progress)
        clock.finished.connect(self.settle)
        return clock

    def apply_now(self, wanted):
        """Reduced motion: the card is simply there, or not."""
        self.wanted = wanted
        self.settle()

    # -- painting ---------------------------------------------------------------
    def _shadow_pixmap(self, size, ratio):
        key = (round(size.width()), round(size.height()), ratio)
        if key != self._shadow_key:
            width, height = round((size.width() + 2 * SHADOW) * ratio), round((size.height() + 2 * SHADOW) * ratio)
            image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(ratio, ratio)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 120))
            painter.drawRoundedRect(QRectF(SHADOW, SHADOW + 8, size.width(), size.height() - 4),
                                    RADIUS['card'], RADIUS['card'])
            painter.end()
            soft = _soft(_soft(image, 6), 4)
            pixmap = QPixmap.fromImage(soft)
            pixmap.setDevicePixelRatio(ratio)
            self._shadow, self._shadow_key = pixmap, key
        return self._shadow

    def paint(self, painter):
        if self.progress <= 0.:
            return
        theme = self.window.theme
        rect = self.rect()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(min(1., self.progress * 1.6))
        ratio = max(1., self.window.devicePixelRatioF())
        painter.drawPixmap(QPointF(rect.x() - SHADOW, rect.y() - SHADOW), self._shadow_pixmap(rect.size(), ratio))
        body = QPainterPath()
        body.addRoundedRect(rect, RADIUS['card'], RADIUS['card'])
        fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        fill.setColorAt(0., QColor(theme['porcelain_card_top']))
        fill.setColorAt(1., QColor(theme['porcelain_card']))
        painter.fillPath(body, fill)
        edge = QColor(theme['porcelain_edge'])
        painter.setPen(QPen(edge, 1.))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(body)
        highlight = QColor(theme['porcelain_highlight'])
        highlight.setAlphaF(.9)
        painter.setPen(QPen(highlight, 1.))
        painter.drawLine(QPointF(rect.left() + RADIUS['card'], rect.top() + 1.5),
                         QPointF(rect.right() - RADIUS['card'], rect.top() + 1.5))
        if self.pixmap is not None:
            painter.drawPixmap(rect.topLeft().toPoint(), self.pixmap)
        painter.restore()
