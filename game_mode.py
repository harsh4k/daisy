"""Read-only foreground detection; never hooks into or modifies the game."""
import ctypes
from ctypes import wintypes
import sys
import time

import psutil


def foreground_pid():
    if sys.platform != 'win32':
        return 0
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


class GameGuard:
    def __init__(self, foreground_pid=foreground_pid, process_name=None, clock=time.monotonic):
        self.foreground_pid = foreground_pid
        self.process_name = process_name or (lambda pid: psutil.Process(pid).name())
        self.clock = clock
        self._pid = None
        self._expires = 0
        self._active = False

    def is_active(self):
        try:
            pid, now = self.foreground_pid(), self.clock()
            if pid != self._pid or now >= self._expires:
                self._pid, self._expires = pid, now + 2
                self._active = False
                if pid:
                    self._active = self.process_name(pid).casefold() in (
                        'valorant.exe', 'valorant-win64-shipping.exe')
            return self._active
        except (psutil.Error, OSError, AttributeError):
            self._active = False
            return False
