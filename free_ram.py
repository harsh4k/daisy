"""Run the owner's own free-RAM PowerShell script from a button, without a console window.

The script is the owner's file (default X:\\Projects\\Apps\\free-ram.ps1, or the
`free_ram_script` setting). Daisy only starts it hidden and shows its last line,
for example "RAM free: 9.1 GB / 15.7 GB". It runs as the user: no admin rights.
"""
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

DEFAULT_SCRIPT = r'X:\Projects\Apps\free-ram.ps1'
TIMEOUT_MS = 30000


def command(script):
    """The exact powershell arguments: no profile, no console, this one file."""
    return ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-WindowStyle', 'Hidden', '-File', str(script)]


def summary(output, exit_code):
    """One short line for the card from what the script printed."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if exit_code != 0:
        return 'Free RAM failed' + (f': {lines[-1][:80]}' if lines else '')
    return lines[-1][:80] if lines else 'Done'


class FreeRam(QObject):
    started = pyqtSignal()
    finished = pyqtSignal(str)

    def __init__(self, script=None, parent=None):
        super().__init__(parent)
        self.script = Path(script or DEFAULT_SCRIPT)
        self.process = None

    def busy(self):
        return self.process is not None

    def run(self):
        """Start the script once; a second press while it runs does nothing."""
        if self.busy():
            return False
        if not self.script.is_file():
            self.finished.emit(f'Script not found: {self.script}')
            return False
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        process.finished.connect(lambda code, _status: self._done(process, code))
        process.errorOccurred.connect(lambda _error: self._done(process, -1))
        self.process = process
        process.start('powershell.exe', command(self.script))
        self.started.emit()
        # A hung script is stopped; the timer belongs to the process, so it dies with it.
        guard = QTimer(process)
        guard.setSingleShot(True)
        guard.timeout.connect(process.kill)
        guard.start(TIMEOUT_MS)
        return True

    def _done(self, process, code):
        if self.process is not process:
            return
        self.process = None
        output = bytes(process.readAll()).decode('utf-8', 'replace')
        process.deleteLater()
        self.finished.emit(summary(output, code))
