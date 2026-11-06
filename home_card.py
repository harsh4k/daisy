"""A Home card: a washed tile with a label, a ringed glyph, a big title and a detail line.

Three of them are the open island's Home page. Each card is drawn, not laid out:
black at the top, taking on its colour toward the bottom, with one hairline edge.
Pressing a card opens its page; a card may carry one real control (the play disc).
"""
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy

from focus_ring import KeyboardFocusRing
from ui_tokens import numeric_font, resolved_family

RADIUS = 24
INSET = 16
RING = 48
TITLE_SIZES = (34, 30, 26, 22, 20)
MUSIC_SIZES = (20,)


def _font(size, weight):
    result = QFont(resolved_family())
    result.setPixelSize(size)
    result.setWeight(QFont.Weight(weight))
    if size >= 17:
        result.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -.5 if size >= 30 else -.2)
    return result


def draw_glyph(painter, kind, center, color=QColor('white')):
    """The symbol inside a ring or a disc: check, play, pause or stop."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx, cy = center.x(), center.y()
    if kind == 'check':
        painter.setPen(QPen(color, 3., Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPolyline(QPolygonF([QPointF(cx - 8, cy + .5), QPointF(cx - 2.5, cy + 6), QPointF(cx + 8.5, cy - 6)]))
    elif kind == 'play':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([QPointF(cx - 5, cy - 8), QPointF(cx - 5, cy + 8), QPointF(cx + 8, cy)]))
    elif kind == 'pause':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for dx in (-7, 2):
            painter.drawRoundedRect(QRectF(cx + dx, cy - 8, 5, 16), 1.6, 1.6)
    elif kind == 'stop':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(cx - 7.5, cy - 7.5, 15, 15), 3.6, 3.6)
    painter.restore()


class PlayDisc(KeyboardFocusRing, QAbstractButton):
    """The music card's one real control: a white disc with play or pause."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.playing = False
        self.ring = QColor('#ffffff')

    def set_playing(self, playing):
        self.playing = bool(playing)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        disc = QColor('#d8d8dc') if self.isDown() else QColor('#ffffff')
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(disc)
        painter.drawEllipse(QRectF(self.rect()).adjusted(2, 2, -2, -2))
        draw_glyph(painter, 'pause' if self.playing else 'play', QPointF(self.width() / 2, self.height() / 2),
                   QColor('#000000'))
        if self.property('keyboard'):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.ring, 2))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))


class HomeCard(KeyboardFocusRing, QAbstractButton):
    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.theme = None
        self.wash = QColor('#1456d9')
        self.label, self.title, self.detail = '', '', ''
        self.glyph = 'none'
        self.art = None          # a square pixmap, or None
        self.numeric = False     # tabular digits for a timer
        self.control = None      # an optional child control, kept bottom right
        self.title_sizes = TITLE_SIZES
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def sizeHint(self):
        return QSize(181, 176)

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def set_control(self, control):
        self.control = control
        control.setParent(self)
        self._place_control()
        control.show()

    def set_content(self, label, title, detail, glyph='none', wash=None, art=None, numeric=False):
        self.label, self.title, self.detail, self.glyph = label, title, detail, glyph
        self.art, self.numeric = art, numeric
        if wash is not None:
            self.wash = QColor(wash)
        name = ', '.join(part for part in (label, title, detail) if part)
        self.setToolTip(name)
        self.setAccessibleName(name)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_control()

    def _place_control(self):
        if self.control is not None:
            self.control.move(self.width() - INSET + 2 - self.control.width(),
                              self.height() - INSET + 2 - self.control.height())

    def _shell(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), RADIUS, RADIUS)
        return path

    def _top_color(self):
        base = QColor(self.theme['island']) if self.theme else QColor('#000000')
        return QColor.fromHsv(max(0, base.hue()), base.saturation(), min(255, base.value() + 12))

    def fit_title(self, width):
        """The largest title that fits, then an ellipsis: (font, text)."""
        for size in self.title_sizes:
            font = numeric_font(size, 700) if self.numeric else _font(size, 700)
            if QFontMetrics(font).horizontalAdvance(self.title) <= width or self.numeric:
                return font, self.title
        return font, QFontMetrics(font).elidedText(self.title, Qt.TextElideMode.ElideRight, int(width))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        shell = self._shell()
        top = self._top_color()
        fill = QLinearGradient(0, 0, 0, h)
        fill.setColorAt(0., top)
        fill.setColorAt(.3, top)
        fill.setColorAt(1., self.wash)
        painter.fillPath(shell, QBrush(fill))
        painter.save()
        painter.setClipPath(shell)
        glow = QRadialGradient(QPointF(w * .15, h * 1.02), w * .85)
        lit = QColor(self.wash).lighter(135)
        lit.setAlphaF(.55)
        clear = QColor(lit)
        clear.setAlphaF(0.)
        glow.setColorAt(0., lit)
        glow.setColorAt(1., clear)
        painter.fillRect(self.rect(), glow)
        if self.isDown():
            painter.fillRect(self.rect(), QColor(255, 255, 255, 24))
        elif self.underMouse():
            painter.fillRect(self.rect(), QColor(255, 255, 255, 12))
        painter.restore()
        painter.setPen(QPen(QColor(255, 255, 255, 36 if self.underMouse() else 26), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shell)
        if self.property('keyboard') and self.theme:
            painter.setPen(QPen(QColor(self.theme['accent']), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), RADIUS - 1, RADIUS - 1)
        self._paint_content(painter, w, h)

    def _paint_content(self, painter, w, h):
        muted = QColor(self.theme['muted']) if self.theme else QColor('#b1b1b8')
        painter.setFont(_font(13, 400))
        painter.setPen(muted)
        painter.drawText(QRectF(INSET, INSET, w - INSET * 2 - RING - 8, 20),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)
        corner = QPointF(w - INSET - RING / 2, INSET + RING / 2)
        if self.art is not None or self.glyph == 'art':
            self._paint_art(painter, corner)
        elif self.glyph != 'none':
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#ffffff'), 4))
            painter.drawEllipse(QRectF(corner.x() - RING / 2 + 2, corner.y() - RING / 2 + 2, RING - 4, RING - 4))
            draw_glyph(painter, self.glyph, corner)
        reserve = (self.control.width() + 8) if self.control is not None else 0
        font, text = self.fit_title(w - INSET * 2 - reserve)
        painter.setFont(font)
        painter.setPen(QColor('#ffffff'))
        detail_h = 18
        base = h - INSET - detail_h + 2
        line = QFontMetrics(font).height()
        painter.drawText(QRectF(INSET, base - line - 1, w - INSET * 2 - reserve, line),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, text)
        painter.setFont(_font(13, 500))
        painter.setPen(self._detail_color())
        shown = QFontMetrics(painter.font()).elidedText(self.detail, Qt.TextElideMode.ElideRight,
                                                        int(w - INSET * 2 - reserve))
        painter.drawText(QRectF(INSET, base, w - INSET * 2 - reserve, detail_h),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, shown)

    def _detail_color(self):
        tint = QColor(self.wash).lighter(175)
        tint.setHsv(max(0, tint.hue()), min(tint.saturation(), 120), 255)
        return tint

    def _paint_art(self, painter, corner):
        tile = QRectF(corner.x() - 27, corner.y() - 27, 54, 54)
        path = QPainterPath()
        path.addRoundedRect(tile, 14, 14)
        painter.save()
        painter.setClipPath(path)
        if self.art is not None:
            painter.drawPixmap(tile.toRect(), self.art)
        else:
            fill = QLinearGradient(tile.topLeft(), tile.bottomRight())
            fill.setColorAt(0., QColor(self.wash).lighter(150))
            fill.setColorAt(1., QColor(self.wash).darker(130))
            painter.fillPath(path, QBrush(fill))
            painter.setPen(QPen(QColor(255, 255, 255, 235), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            cx, cy = tile.center().x(), tile.center().y()
            painter.drawEllipse(QRectF(cx - 9, cy + 1, 8, 8))
            painter.drawLine(QPointF(cx - 1, cy + 5), QPointF(cx - 1, cy - 9))
            painter.drawLine(QPointF(cx - 1, cy - 9), QPointF(cx + 8, cy - 6))
        painter.restore()
