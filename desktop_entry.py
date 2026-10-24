"""Own the application lifetime, including releasing the lock before restart."""
import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox
from app_runtime import configure_application, acquire_instance_lock, launch_restart
from runtime_diagnostics import configure_diagnostics, shutdown_diagnostics, enable_fatal_capture
from runtime_tray import RuntimeTray
from approval_bridge import ApprovalBridge


def run(island_type):
    app = QApplication.instance() or QApplication(sys.argv)
    configure_application(app)
    try:
        configure_diagnostics()
    except OSError:
        # A read-only profile should not prevent the overlay from opening.
        logging.getLogger(__name__).warning('startup_failed')
    lock = None
    island = None
    approvals = None
    code = 0
    try:
        lock = acquire_instance_lock()
        if lock is None:
            logging.getLogger(__name__).info('instance_already_running')
            return 0
        app.setQuitOnLastWindowClosed(False)
        enable_fatal_capture()
        island = island_type()
        if hasattr(island, 'attach_approval_bridge'):
            approvals = ApprovalBridge(parent=island)
            approvals.start()
            island.attach_approval_bridge(approvals)
        if hasattr(island, 'start_monitors'):
            island.start_monitors()
        island.runtime_tray = RuntimeTray(island, island.open_settings,
            island.request_restart, island.open_logs, island.close)
        island.show()
        logging.getLogger(__name__).info('startup_ready')
        code = app.exec()
    except Exception:
        logging.getLogger(__name__).exception('startup_failed')
        QMessageBox.critical(None, 'Daisy could not start',
                             'Daisy could not start. Open the local logs for details.')
        code = 1
    finally:
        if approvals is not None:
            approvals.close()
        if code and island is not None:
            island.close()
            # A failed tray/show must not release the instance lock over live workers.
            for name in ('perf_monitor', 'media_monitor', 'key_monitor', 'notif_monitor', 'weather_monitor'):
                monitor = getattr(island, name, None)
                if monitor is not None:
                    monitor.stop()
                    if hasattr(monitor, 'wait'):
                        monitor.wait(3000)
        if island is not None and hasattr(island, 'runtime_tray'):
            island.runtime_tray.tray.hide()
        if lock is not None:
            lock.unlock()
        if island is not None and island.restart_requested:
            if not launch_restart():
                QMessageBox.critical(None, 'Daisy could not restart',
                                     'Open Daisy from Start to try again. Your settings are preserved.')
                code = 1
        logging.getLogger(__name__).info('shutdown_complete')
        shutdown_diagnostics()
    return code
