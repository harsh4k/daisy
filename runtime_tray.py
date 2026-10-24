"""Persistent recovery controls, independent of foreground overlay visibility."""
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from app_runtime import get_startup_status
from branding import app_icon


class RuntimeTray(QObject):
    def __init__(self, parent, open_settings, restart, open_logs, quit_app):
        super().__init__(parent)
        self.menu = QMenu()
        self.status_action = self.menu.addAction('Startup: Unavailable')
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        for label, callback in [('Open Settings', open_settings), ('Restart Daisy', restart),
                                ('Open Logs', open_logs), ('Quit Daisy', quit_app)]:
            action = self.menu.addAction(label)
            action.triggered.connect(lambda checked=False, call=callback: call())
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip('Daisy')
        self.tray.setContextMenu(self.menu)
        self.menu.aboutToShow.connect(self.refresh)
        self.tray.activated.connect(lambda reason: open_settings()
                                   if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.refresh()
        self.tray.show()

    def refresh(self):
        status = get_startup_status()
        self.status_action.setText('Startup: ' + status['state'])
        self.status_action.setToolTip(status['detail'])
