"""Application identity, single-instance protection, and opt-in startup."""
from pathlib import Path
import logging
import subprocess
import sys
import winreg

from PyQt6.QtCore import QLockFile, QStandardPaths

from branding import APP_NAME, app_icon, configure_fonts

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def configure_application(app):
    configure_fonts(app)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())


def acquire_instance_lock(lock_dir=None):
    """Return a retained lock, or None when another Daisy is already alive."""
    directory = Path(lock_dir or QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation))
    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(directory / "daisy.lock"))
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        return lock
    if lock.error() == QLockFile.LockError.LockFailedError:
        return None
    raise OSError('Daisy could not create its instance lock; check local app-data permissions and disk space.')


def startup_command():
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    if executable.name.lower() == "python.exe":
        windowed = executable.with_name("pythonw.exe")
        if windowed.exists():
            executable = windowed
    script = Path(__file__).resolve().with_name("main.py")
    return f'"{executable}" "{script}"'


def set_autostart(enabled):
    """Update Daisy's entry without bypassing Windows' Startup Apps setting."""
    try:
        access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            try:
                legacy, _ = winreg.QueryValueEx(key, "DynamicIsland")
                if "dynamicisland" in legacy.lower() or "dynamic-island" in legacy.lower():
                    winreg.DeleteValue(key, "DynamicIsland")
            except FileNotFoundError:
                pass
        return True
    except OSError:
        logging.getLogger(__name__).exception("Could not update startup preference")
        return False


def _read_entry(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_QUERY_VALUE) as key:
            return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None


def get_startup_status():
    """Report Windows' decision without changing StartupApproved disablement."""
    result = {'state': 'Unavailable', 'detail': 'Could not read Windows startup settings.',
              'command': ''}
    try:
        entry = _read_entry(RUN_KEY, APP_NAME)
        if entry is None or not isinstance(entry[0], str) or not entry[0].strip():
            return {**result, 'state': 'Off', 'detail': 'Daisy is not registered at sign-in.'}
        result['command'] = entry[0]
        approval = _read_entry(APPROVED_KEY, APP_NAME)
        if approval is not None:
            data = approval[0]
            if not isinstance(data, bytes) or not data or data[0] not in (2, 3, 6, 7):
                return {**result, 'detail': 'Windows startup approval could not be interpreted.'}
            if data[0] in (3, 7):
                return {**result, 'state': 'Disabled in Windows',
                        'detail': 'Enable Daisy in Windows Settings > Apps > Startup.'}
        return {**result, 'state': 'Enabled', 'detail': 'Daisy is registered at sign-in.'}
    except OSError:
        return result


def capture_startup_entries():
    """Snapshot only the two Run values that set_autostart can change.

    Read errors propagate: callers must not begin a transaction without a backup.
    StartupApproved is deliberately neither changed nor restored.
    """
    return {name: _read_entry(RUN_KEY, name) for name in (APP_NAME, 'DynamicIsland')}


def restore_startup_entries(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {APP_NAME, 'DynamicIsland'}:
        return False
    for entry in snapshot.values():
        if entry is not None and (not isinstance(entry, (tuple, list)) or len(entry) != 2):
            return False
    try:
        access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access) as key:
            for name, entry in snapshot.items():
                if entry is not None:
                    value, kind = entry
                    winreg.SetValueEx(key, name, 0, kind, value)
                else:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
        return True
    except OSError:
        logging.getLogger(__name__).exception('startup_restore_failed')
        return False


def restart_command():
    """Return argv, never a shell string or the current test-runner arguments."""
    if getattr(sys, 'frozen', False):
        return [sys.executable]
    executable = Path(sys.executable)
    windowed = executable.with_name('pythonw.exe')
    if executable.name.lower() == 'python.exe' and windowed.exists():
        executable = windowed
    return [str(executable), str(Path(__file__).resolve().with_name('main.py'))]


def launch_restart():
    """Launch once; the coordinator must release its QLockFile before calling."""
    command = restart_command()
    directory = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) \
        else Path(__file__).resolve().parent
    try:
        subprocess.Popen(command, cwd=str(directory), shell=False,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        logging.getLogger(__name__).info('restart_launched')
        return True
    except OSError:
        logging.getLogger(__name__).exception('restart_failed')
        return False
