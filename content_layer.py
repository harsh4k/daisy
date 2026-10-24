"""Animate a picture of the island's content instead of live widgets.

While the shell moves, the live widgets are hidden and one cached snapshot is
drawn inside the island's anti-aliased outline. Nothing re-lays out, no widget
is re-rendered through a graphics effect, and only the island area repaints.
At rest the live widgets return, untouched.
"""
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QApplication

SOFTEN = 6  # downscale factor for the cheap blur used while content arrives


def _soften(pixmap):
    """A blurred copy: shrink, then smoothly scale back up."""
    size = pixmap.size()
    small = pixmap.scaled(max(1, size.width() // SOFTEN), max(1, size.height() // SOFTEN),
                          Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
    soft = small.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
    soft.setDevicePixelRatio(pixmap.devicePixelRatio())
    return soft


class ContentLayer:
    """The content as the shell shows it: live at rest, a snapshot while moving.

    `opacity()`/`setOpacity()` keep the shape of the effect they replace, so the
    motion code and its tests read one value for how visible the content is.
    """

    def __init__(self, window):
        self.window = window
        self._opacity = 1.
        self.rise = 0
        self.sharpness = 1.
        self.pixmap = None
        self.soft = None
        self.width = 0
        self.active = False

    # -- visibility values ----------------------------------------------------
    def opacity(self):
        return self._opacity

    def setOpacity(self, value):
        value = max(0., min(1., float(value)))
        if value != self._opacity:
            self._opacity = value
            if self.active:
                self.window.update_island_region()

    def set_reveal(self, opacity, rise, sharpness):
        changed = (opacity, rise, sharpness) != (self._opacity, self.rise, self.sharpness)
        self._opacity, self.rise, self.sharpness = opacity, rise, sharpness
        if changed and self.active:
            self.window.update_island_region()

    # -- snapshot lifecycle ---------------------------------------------------
    def capture(self):
        """Picture the content as it is now and hide the live widgets."""
        window = self.window
        container = window.content_container
        self.pixmap = self.soft = None
        focus = QApplication.focusWidget()
        if focus is not None and window.island_root.isAncestorOf(focus):
            # Hiding a focused control would move keyboard focus or end an edit;
            # the content changes in place instead.
            self.release()
            return
        if not container.isHidden():
            window.content_layout.activate()
            QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            self.pixmap = container.grab()
            self.soft = _soften(self.pixmap)
            self.width = container.width()
        self.active = True
        window.island_root.hide()
        window.update_island_region()

    def release(self):
        """Bring the live widgets back and drop the picture."""
        window = self.window
        was_active = self.active
        self.active = False
        self.pixmap = self.soft = None
        self.rise, self.sharpness = 0, 1.
        if window.island_root.isHidden():
            window.island_root.show()
        if was_active:
            window.update_island_geometry(window.get_island_rect(), window.get_current_radius())
            window.update_island_region()

    # -- painting -------------------------------------------------------------
    def paint(self, painter, rect):
        """Draw the snapshot where the live content sits; the caller clips it."""
        if not self.active or self.pixmap is None or self._opacity <= 0.:
            return
        x = int(rect.x()) + int((rect.width() - self.width) / 2)
        y = int(rect.y()) + self.rise
        painter.save()
        if self.sharpness < 1. and self.soft is not None:
            painter.setOpacity(self._opacity * (1. - self.sharpness))
            painter.drawPixmap(x, y, self.soft)
        painter.setOpacity(self._opacity * self.sharpness)
        painter.drawPixmap(x, y, self.pixmap)
        painter.restore()
