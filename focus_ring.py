"""Focus rings for keyboard focus only, as on macOS.

A click or the window becoming active gives focus without a ring; Tab, a
shortcut or code that moves focus deliberately shows it. Styles use the
`keyboard` property: QSS like `#Name[keyboard="true"] {{ border-color: … }}`.
"""
from PyQt6.QtCore import Qt

KEYBOARD = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason, Qt.FocusReason.OtherFocusReason)


class KeyboardFocusRing:
    def focusInEvent(self, event):
        self._show_ring(event.reason() in KEYBOARD)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._show_ring(False)
        super().focusOutEvent(event)

    def _show_ring(self, on):
        if self.property('keyboard') != on:
            self.setProperty('keyboard', on)
            self.style().unpolish(self)
            self.style().polish(self)
