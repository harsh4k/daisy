"""Windows calls behind Gaming and College modes; the engine reaches the system only here."""
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import winreg

import psutil

from game_mode import foreground_pid

GPU_KEY = r'Software\Microsoft\DirectX\UserGpuPreferences'
OLLAMA = 'http://127.0.0.1:11434'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PROCESS_SUSPEND_RESUME = 0x0800
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class _GUID(ctypes.Structure):
    _fields_ = [('data', ctypes.c_ubyte * 16)]


def _current_user():
    try:
        return psutil.Process().username().casefold()
    except psutil.Error:
        return ''


class WindowsBackend:
    """Every method reports failure as False, None or an empty list; none raises."""

    def __init__(self):
        self.own_pid = os.getpid()
        self.user = _current_user()

    def foreground_pid(self):
        return foreground_pid()

    def user_processes(self):
        """Processes owned by the signed-in user: pid, name, create_time and exe path."""
        found = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'create_time', 'exe']):
            info = proc.info
            if not info.get('name') or (info.get('username') or '').casefold() != self.user:
                continue
            found.append({'pid': info['pid'], 'name': info['name'],
                          'create_time': info.get('create_time') or 0.0, 'exe': info.get('exe') or ''})
        return found

    def process_matches(self, pid, create_time):
        try:
            return abs(psutil.Process(pid).create_time() - create_time) < 0.01
        except psutil.Error:
            return False

    def _process_call(self, pid, function):
        if sys.platform != 'win32':
            return False
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            return getattr(ctypes.windll.ntdll, function)(handle) == 0
        finally:
            kernel32.CloseHandle(handle)

    def suspend(self, pid):
        return self._process_call(pid, 'NtSuspendProcess')

    def resume(self, pid):
        return self._process_call(pid, 'NtResumeProcess')

    def get_power_scheme(self):
        if sys.platform != 'win32':
            return None
        pointer = ctypes.POINTER(_GUID)()
        if ctypes.windll.powrprof.PowerGetActiveScheme(None, ctypes.byref(pointer)) != 0:
            return None
        try:
            return str(uuid.UUID(bytes_le=bytes(pointer.contents.data)))
        finally:
            ctypes.windll.kernel32.LocalFree(pointer)

    def set_power_scheme(self, scheme):
        if sys.platform != 'win32':
            return False
        guid = _GUID((ctypes.c_ubyte * 16)(*uuid.UUID(scheme).bytes_le))
        return ctypes.windll.powrprof.PowerSetActiveScheme(None, ctypes.byref(guid)) == 0

    def get_gpu_pref(self, path):
        """The stored preference string for one executable, or None when it has none."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, GPU_KEY) as key:
                value, _ = winreg.QueryValueEx(key, path)
                return value if isinstance(value, str) else None
        except OSError:
            return None

    def set_gpu_pref(self, path, value):
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, GPU_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if value is None:
                    winreg.DeleteValue(key, path)
                else:
                    winreg.SetValueEx(key, path, 0, winreg.REG_SZ, value)
            return True
        except FileNotFoundError:
            return value is None
        except OSError:
            return False

    def _ollama(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(OLLAMA + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=4) as response:
            return json.load(response)

    def unload_ollama(self):
        """Unload every loaded model; returns (name, bytes of GPU memory it held)."""
        try:
            models = self._ollama('/api/ps').get('models') or []
        except (OSError, ValueError, urllib.error.URLError):
            return []
        unloaded = []
        for model in models:
            name = model.get('name') or model.get('model')
            if not name:
                continue
            try:
                self._ollama('/api/generate', {'model': name, 'keep_alive': 0})
            except (OSError, ValueError, urllib.error.URLError):
                continue
            unloaded.append((name, int(model.get('size_vram') or 0)))
        return unloaded

    def screen_on_nvidia(self):
        """True when the primary display is wired to the NVIDIA GPU (a MUX set to discrete only)."""
        if sys.platform != 'win32':
            return False

        class Device(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('name', wintypes.WCHAR * 32), ('adapter', wintypes.WCHAR * 128),
                        ('flags', wintypes.DWORD), ('id', wintypes.WCHAR * 128), ('key', wintypes.WCHAR * 128)]
        index = 0
        while True:
            device = Device()
            device.cb = ctypes.sizeof(device)
            if not ctypes.windll.user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
                return False
            if device.flags & 4:
                return 'nvidia' in device.adapter.casefold()
            index += 1

    def nvidia_apps(self):
        """Names of apps holding the NVIDIA GPU right now (this one query wakes it briefly)."""
        try:
            result = subprocess.run(['nvidia-smi', '--query-compute-apps=process_name',
                                     '--format=csv,noheader'], capture_output=True, text=True,
                                    timeout=6, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return []
        windows = os.environ.get('SystemRoot', r'C:\Windows').casefold()
        names = {os.path.basename(path) for path in (line.strip() for line in result.stdout.splitlines())
                 if path and not path.casefold().startswith(windows)}
        return sorted(names, key=str.casefold)
