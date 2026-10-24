"""Keep the transparent overlay window only as large as the island needs.

Windows re-uploads a whole translucent (layered) window for every repaint, so
its size is the real cost of each frame. At rest the overlay hugs the island;
it grows before a transition starts, never during one, and shrinks once the
motion settles. The island stays centred, so resizing never moves it.
"""
from PyQt6.QtCore import QPoint

MARGIN_X = 48       # rim aura, notch ears and a soft glow either side
MARGIN_BOTTOM = 56  # glow under the island
HEADROOM = 1.12     # springs overshoot about 9-12% before they settle
DEFAULT_CAP = (1200, 700)


def island_top(window):
    return 0 if window.current_state == 'Hidden' or window.island_style == 'Notch Nook' else 10


def needed_size(window, island_w, island_h, springy=False):
    scale = HEADROOM if springy else 1.
    width = max(int(island_w * scale) + 2 * MARGIN_X, int(window.overlay_min_width()))
    width += width % 2  # even, so the centred island keeps whole pixels
    height = island_top(window) + int(island_h * scale) + MARGIN_BOTTOM + int(round(window.overlay_extra_height()))
    return width, height


def caps(window):
    available = window.screen().availableGeometry()
    if window.compatibility_mode:
        # Compatibility mode lets the overlay use the whole screen when needed.
        return available.width(), available.height()
    return min(DEFAULT_CAP[0], available.width()), min(DEFAULT_CAP[1], available.height())


def fit(window, width, height):
    """Resize and centre the overlay on the screen's top edge, if anything changed."""
    cap_w, cap_h = caps(window)
    width, height = min(width, cap_w), min(height, cap_h)
    if (window.width(), window.height()) != (width, height):
        window.setFixedSize(width, height)
    target = QPoint(window.get_centered_x(width), window.screen().availableGeometry().y())
    if window.pos() != target:
        window.move(target)


def grow_for(window, start, end, springy):
    """Before motion: make room for both shapes and any overshoot, never shrinking."""
    need = [max(a, b) for a, b in zip(needed_size(window, *start), needed_size(window, *end, springy=springy))]
    fit(window, max(window.width(), need[0]), max(window.height(), need[1]))


def rest(window):
    """After motion: hug the island as it is now."""
    fit(window, *needed_size(window, window.island_w, window.island_h))
