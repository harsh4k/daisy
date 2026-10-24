"""Browser detection follows GameGuard's cached, read-only foreground pattern."""
import os
import ctypes
from ctypes import wintypes
import time

import psutil
from game_mode import foreground_pid


class BrowserGuard:
    def __init__(self, foreground_pid=foreground_pid, process_name=None, clock=time.monotonic):
        self.foreground_pid = foreground_pid
        self.process_name = process_name or (lambda pid: psutil.Process(pid).name())
        self.clock = clock
        self._pid = None
        self._expires = 0
        self._browser = False
        self._browser_hwnd = None

    def is_active(self):
        try:
            pid, now = self.foreground_pid(), self.clock()
            # Deliberately opening Daisy or its editor must not restore hover mode.
            if pid == os.getpid():
                return self._browser
            if pid != self._pid or now >= self._expires:
                self._pid, self._expires = pid, now + 2
                self._browser = False
                if pid:
                    self._browser = self.process_name(pid).casefold() in (
                        'chrome.exe', 'brave.exe', 'msedge.exe', 'firefox.exe',
                        'opera.exe', 'vivaldi.exe', 'arc.exe')
            if self._browser:
                self._browser_hwnd = ctypes.windll.user32.GetForegroundWindow()
            return self._browser
        except (psutil.Error, OSError, AttributeError):
            self._browser = False
            return False

    def restore_focus(self):
        """Return intentional panel focus only when Daisy still owns it."""
        try:
            user32 = ctypes.windll.user32
            user32.IsWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            if (self._browser_hwnd and self.foreground_pid() == os.getpid()
                    and user32.IsWindow(self._browser_hwnd)):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(self._browser_hwnd, ctypes.byref(pid))
                if pid.value == self._pid:
                    user32.SetForegroundWindow(self._browser_hwnd)
        except (OSError, AttributeError):
            pass
