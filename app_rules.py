"""Exact executable policies using the read-only, cached GameGuard pattern."""
import ctypes
from ctypes import wintypes
import os
import re
import time

import psutil

MODES = {'hover': 'Hover', 'click': 'Click to open', 'hidden': 'Hidden'}
DEFAULT_RULES = dict.fromkeys(('chrome.exe', 'brave.exe', 'msedge.exe',
    'firefox.exe', 'opera.exe', 'vivaldi.exe', 'arc.exe'), 'click')
DEFAULT_RULES.update(dict.fromkeys(('valorant.exe', 'valorant-win64-shipping.exe'), 'hidden'))


def normalize_rules(value):
    """Validate user overrides; paths and ambiguous case-folded duplicates fail."""
    if not isinstance(value, dict):
        raise ValueError('App rules must be a list of executable names and behaviors.')
    result = {}
    for executable, mode in value.items():
        if not isinstance(executable, str) or re.search(r'[\x00-\x1f\\/:*?"<>|]', executable):
            raise ValueError('Use an executable name, such as chrome.exe, without a path.')
        name = executable.strip().casefold()
        if not name.endswith('.exe') or len(name) <= 4 or name in result or name.startswith('.'):
            raise ValueError('Executable names must be unique and end with .exe.')
        if not isinstance(mode, str) or mode not in MODES:
            raise ValueError('Choose Hover, Click to open, or Hidden.')
        result[name] = mode
    return result


def _user32():
    api = ctypes.windll.user32
    api.GetForegroundWindow.restype = wintypes.HWND
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.IsWindow.argtypes = [wintypes.HWND]
    api.SetForegroundWindow.argtypes = [wintypes.HWND]
    return api


def _window_pid(hwnd):
    pid = wintypes.DWORD()
    if hwnd:
        _user32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _foreground():
    hwnd = _user32().GetForegroundWindow()
    return hwnd, _window_pid(hwnd)


class ForegroundPolicy:
    """Keep external identity while Daisy owns focus; cache names, never HWNDs."""
    def __init__(self, rules=None, foreground=None, process_name=None,
                 clock=time.monotonic, own_pid=None, is_window=None,
                 window_pid=None, activate=None):
        self.foreground = foreground or _foreground
        self.process_name = process_name or (lambda pid: psutil.Process(pid).name())
        self.clock = clock
        self.own_pid = os.getpid() if own_pid is None else own_pid
        self.is_window = is_window or (lambda hwnd: bool(_user32().IsWindow(hwnd)))
        self.window_pid = window_pid or _window_pid
        self.activate = activate or (lambda hwnd: _user32().SetForegroundWindow(hwnd))
        self._pid = None
        self._name = ''
        self._expires = 0
        self._external_hwnd = None
        self.set_rules({} if rules is None else rules)

    def set_rules(self, rules):
        self.rules = normalize_rules(rules)

    def mode(self):
        try:
            hwnd, pid = self.foreground()
            if pid == self.own_pid:
                return self.rules.get(self._name, DEFAULT_RULES.get(self._name, 'hover'))
            if not pid or not hwnd:
                return 'hover'
            now = self.clock()
            if pid != self._pid or now >= self._expires:
                self._pid, self._expires, self._name = pid, now + 2, ''
                self._name = self.process_name(pid).casefold()
            self._external_hwnd = hwnd
            return self.rules.get(self._name, DEFAULT_RULES.get(self._name, 'hover'))
        except (psutil.Error, OSError, AttributeError, KeyError, TypeError, ValueError):
            self._name, self._external_hwnd = '', None
            return 'hover'

    def restore_focus(self):
        """Restore only our last external live window, while Daisy still owns focus."""
        try:
            _, pid = self.foreground()
            hwnd = self._external_hwnd
            if (pid == self.own_pid and hwnd and self.is_window(hwnd)
                    and self.window_pid(hwnd) == self._pid):
                self.activate(hwnd)
        except (psutil.Error, OSError, AttributeError, TypeError, ValueError):
            pass


class RuleGuard:
    def __init__(self, policy, mode):
        if mode not in MODES:
            raise ValueError('Unknown foreground mode')
        self.policy, self.expected_mode = policy, mode

    def is_active(self):
        return self.policy.mode() == self.expected_mode

    def restore_focus(self):
        self.policy.restore_focus()
