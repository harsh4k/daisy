"""Gaming and College modes: journal each change before making it, so any exit can undo it.

The engine has no Qt and reaches Windows only through its backend (mode_system.WindowsBackend),
so tests run it against a fake. A crash leaves the journal behind; recover() undoes it next start.
"""
import json
import os
import time

HIGH_PERFORMANCE = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
BALANCED = '381b4222-f694-41f0-9685-ff5bb260df2e'
SCHEMES = {'gaming': HIGH_PERFORMANCE, 'college': BALANCED}
SCHEME_NAMES = {HIGH_PERFORMANCE: 'High performance', BALANCED: 'Balanced'}
MODE_NAMES = {'gaming': 'Gaming mode', 'college': 'College mode'}

# Never frozen: Windows itself, Daisy, AI agents that may be mid-task, voice chat, the game,
# its launcher and anti-cheat, and Ollama (Loom restarts it if it disappears).
PROTECTED = frozenset(name.casefold() for name in (
    'System', 'Registry', 'smss.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe', 'services.exe',
    'lsass.exe', 'svchost.exe', 'dwm.exe', 'explorer.exe', 'sihost.exe', 'ctfmon.exe', 'conhost.exe',
    'fontdrvhost.exe', 'audiodg.exe', 'RuntimeBroker.exe', 'SearchHost.exe', 'ShellHost.exe',
    'StartMenuExperienceHost.exe', 'ShellExperienceHost.exe', 'TextInputHost.exe',
    'Daisy.exe', 'python.exe', 'pythonw.exe', 'claude.exe', 'codex.exe', 'Discord.exe',
    'valorant.exe', 'valorant-win64-shipping.exe', 'vgc.exe', 'vgtray.exe',
    'RiotClientServices.exe', 'Riot Client.exe', 'RiotClientUx.exe', 'RiotClientCrashHandler.exe',
    'ollama.exe', 'ollama app.exe', 'llama-server.exe'))

DEFAULTS = {
    'gaming_freeze': ['ChatGPT.exe'],
    'college_freeze': ['ChatGPT.exe'],
    'college_gpu_saving': ['brave.exe', 'Discord.exe', 'Spotify.exe', 'ChatGPT.exe', 'Loom.exe',
                           'steam.exe', 'steamwebhelper.exe'],
    'auto_gaming': False,
    'auto_college': False,
}


def normalize_mode_settings(value):
    """Keep valid choices, fill the rest from DEFAULTS; never raises."""
    value = value if isinstance(value, dict) else {}
    result = {}
    for key, default in DEFAULTS.items():
        item = value.get(key, default)
        if isinstance(default, bool):
            result[key] = item if type(item) is bool else default
            continue
        names = item if isinstance(item, list) else default
        clean = []
        for name in names:
            if (isinstance(name, str) and name.casefold().endswith('.exe') and '\\' not in name
                    and '/' not in name and name.casefold() not in {n.casefold() for n in clean}):
                clean.append(name.strip())
        result[key] = clean
    return result


def with_power_saving(old):
    """Set GpuPreference=1 (the integrated GPU) and keep any other stored settings."""
    parts = [part for part in (old or '').split(';') if part and not part.startswith('GpuPreference=')]
    return ';'.join(parts + ['GpuPreference=1']) + ';'


def gigabytes(size):
    return f'{size / 1024 ** 3:.1f} GB'


class ModeEngine:
    def __init__(self, backend, journal_path, clock=time.time):
        self.backend = backend
        self.journal_path = journal_path
        self.clock = clock
        self.journal = self._read()

    @property
    def active(self):
        return self.journal.get('mode') if self.journal else None

    @property
    def auto_started(self):
        return bool(self.journal and self.journal.get('auto'))

    def _read(self):
        try:
            with open(self.journal_path, encoding='utf-8') as stream:
                data = json.load(stream)
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get('mode') in MODE_NAMES else None

    def _write(self):
        temporary = self.journal_path + '.tmp'
        with open(temporary, 'w', encoding='utf-8') as stream:
            json.dump(self.journal, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.journal_path)

    def activate(self, mode, settings, protected=(), auto=False):
        """Apply a mode; returns plain-language lines describing what changed."""
        if mode not in MODE_NAMES:
            raise ValueError(f'Unknown mode: {mode}')
        if self.active == mode:
            return []
        lines = self.deactivate() if self.active else []
        settings = normalize_mode_settings(settings)
        self.journal = {'mode': mode, 'auto': auto, 'started': self.clock(),
                        'power_prev': None, 'frozen': [], 'gpu_prefs': []}
        self._write()
        lines.append(self._apply_power(mode))
        unloaded = self.backend.unload_ollama()
        if unloaded:
            freed = sum(size for _, size in unloaded)
            lines.append(f'Unloaded {", ".join(name for name, _ in unloaded)}'
                         + (f' ({gigabytes(freed)} of GPU memory)' if freed else ''))
        lines.append(self._freeze(settings[f'{mode}_freeze'], protected))
        if mode == 'college':
            if self.backend.screen_on_nvidia():
                lines.append('Screen runs on the NVIDIA GPU, so it never sleeps: switch display mode to '
                             'Optimus (hybrid) for real savings')
            lines.append(self._prefer_intel(settings['college_gpu_saving']))
            still = self.backend.nvidia_apps()
            if still:
                shown = ', '.join(still[:4]) + (f' and {len(still) - 4} more' if len(still) > 4 else '')
                lines.append('Still on the NVIDIA GPU: ' + shown)
        return [line for line in lines if line]

    def _apply_power(self, mode):
        target, previous = SCHEMES[mode], self.backend.get_power_scheme()
        if previous is None or previous == target:
            return f'{SCHEME_NAMES[target]} power plan' if previous == target else ''
        self.journal['power_prev'] = previous
        self._write()
        if self.backend.set_power_scheme(target):
            return f'{SCHEME_NAMES[target]} power plan'
        self.journal['power_prev'] = None
        self._write()
        return 'Could not change the power plan'

    def _freeze(self, names, protected):
        wanted = {name.casefold() for name in names} - PROTECTED - {p.casefold() for p in protected}
        skip = {self.backend.own_pid, self.backend.foreground_pid()}
        frozen, refused = set(), set()
        for proc in self.backend.user_processes():
            if proc['name'].casefold() not in wanted or proc['pid'] in skip:
                continue
            self.journal['frozen'].append({key: proc[key] for key in ('pid', 'name', 'create_time')})
            self._write()
            if self.backend.suspend(proc['pid']):
                frozen.add(proc['name'])
            else:
                self.journal['frozen'].pop()
                self._write()
                refused.add(proc['name'])
        parts = []
        if frozen:
            parts.append('Froze ' + ', '.join(sorted(frozen, key=str.casefold)))
        if refused - frozen:
            parts.append('could not freeze ' + ', '.join(sorted(refused - frozen, key=str.casefold)))
        if refused & frozen:
            parts.append('parts of ' + ', '.join(sorted(refused & frozen, key=str.casefold)) + ' stayed running')
        return '; '.join(parts)

    def _prefer_intel(self, names):
        wanted = {name.casefold() for name in names}
        paths = sorted({proc['exe'] for proc in self.backend.user_processes()
                        if proc['exe'] and proc['name'].casefold() in wanted})
        moved = []
        for path in paths:
            old = self.backend.get_gpu_pref(path)
            new = with_power_saving(old)
            if new == old:
                continue
            self.journal['gpu_prefs'].append({'path': path, 'old': old})
            self._write()
            if self.backend.set_gpu_pref(path, new):
                moved.append(os.path.basename(path))
            else:
                self.journal['gpu_prefs'].pop()
                self._write()
        if not moved:
            return ''
        return 'Intel GPU next launch: ' + ', '.join(sorted(set(moved), key=str.casefold))

    def deactivate(self):
        """Undo everything the journal records; safe to call twice or after a crash."""
        if not self.journal:
            return []
        mode = self.journal['mode']
        resumed, problems = set(), []
        for entry in list(self.journal.get('frozen', [])):
            if self.backend.process_matches(entry['pid'], entry['create_time']):
                if self.backend.resume(entry['pid']):
                    resumed.add(entry['name'])
                else:
                    problems.append(f"could not unfreeze {entry['name']}")
            self.journal['frozen'].remove(entry)
            self._write()
        for entry in list(self.journal.get('gpu_prefs', [])):
            if not self.backend.set_gpu_pref(entry['path'], entry['old']):
                problems.append(f"could not restore the GPU choice for {os.path.basename(entry['path'])}")
            self.journal['gpu_prefs'].remove(entry)
            self._write()
        previous = self.journal.get('power_prev')
        if previous:
            if not self.backend.set_power_scheme(previous):
                problems.append('could not restore the power plan')
            self.journal['power_prev'] = None
            self._write()
        self.journal = None
        try:
            os.remove(self.journal_path)
        except FileNotFoundError:
            pass
        lines = [f'{MODE_NAMES[mode]} off']
        if resumed:
            lines.append('Unfroze ' + ', '.join(sorted(resumed, key=str.casefold)))
        return lines + problems

    def recover(self):
        """After a crash or reboot: undo a mode the last session left on."""
        return self.deactivate() if self.journal else []
