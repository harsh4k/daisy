"""Connect Gaming and College modes to the island: the Tools tab, auto-start and a safe exit."""
import datetime
import logging
import os
import threading
import time

import psutil
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog

from app_rules import DEFAULT_RULES
from branding import APP_NAME
from mode_engine import MODE_NAMES, ModeEngine, normalize_mode_settings
from mode_insights import BatteryForecast, GpuSampler, clock_text
from mode_system import WindowsBackend
from modes_panel import AppChooser, ModesPanel

TICK_MS = 5000
GAME_GRACE = 30


class _Relay(QObject):
    """Carries a worker thread's result back to the UI thread."""
    finished = pyqtSignal(object, object, object)


class ModeWiringMixin:
    def create_modes_tab(self, backend=None):
        self.mode_settings = normalize_mode_settings(self.settings.get('modes'))
        self.settings['modes'] = self.mode_settings
        journal = os.path.join(os.path.dirname(self.config_path), 'mode_state.json')
        self.mode_engine = ModeEngine(backend or WindowsBackend(), journal)
        self.gpu_sampler = GpuSampler()
        self.battery_forecast = BatteryForecast()
        self._mode_busy = False
        self._mode_worker = None
        self._mode_lines = {}
        self._mode_report = ''
        self._game_seen_at = 0.0
        self._game_auto_blocked = False
        self._was_plugged = None
        self._forecast_warned = None
        self._mode_relay = _Relay(self)
        self._mode_relay.finished.connect(self._mode_finished)
        self.modes_panel = ModesPanel()
        self.tools_panel.modes_panel = self.modes_panel
        self.tools_panel.tabs.addTab(self.modes_panel, 'Modes')
        self.modes_panel.set_theme(self.theme)
        self.modes_panel.set_auto(self.mode_settings)
        self.modes_panel.set_active(self.mode_engine.active)
        self.modes_panel.toggled.connect(lambda mode, on: self.set_mode(mode if on else None))
        self.modes_panel.auto_changed.connect(self._set_mode_auto)
        self.modes_panel.choose_apps.connect(self.choose_mode_apps)
        self.mode_timer = QTimer(self)
        self.mode_timer.timeout.connect(self.tick_modes)
        self.mode_timer.start(TICK_MS)

    def _hidden_games(self):
        rules = dict(DEFAULT_RULES)
        rules.update(self.settings.get('app_rules') or {})
        return {name for name, rule in rules.items() if rule == 'hidden'}

    def set_mode(self, target, auto=False):
        """Turn a mode on (switching from the other one) or, with None, turn modes off."""
        active = self.mode_engine.active
        if self._mode_busy or target == active:
            self.modes_panel.set_active(active, self._mode_busy)
            return
        if active == 'gaming' and target is None and not auto and self._game_running():
            self._game_auto_blocked = True
        self._mode_busy = True
        self.modes_panel.set_active(target or active, busy=True)
        if active == 'gaming':
            self._mode_report = self.gpu_sampler.stop()
        settings, protected = dict(self.mode_settings), self._hidden_games()

        def work():
            try:
                lines = (self.mode_engine.activate(target, settings, protected, auto) if target
                         else self.mode_engine.deactivate())
                self._mode_relay.finished.emit(active, lines, None)
            except OSError as error:
                self._mode_relay.finished.emit(active, [], error)

        self._mode_worker = threading.Thread(target=work, name='daisy-mode', daemon=True)
        self._mode_worker.start()

    def _mode_finished(self, previous, lines, error):
        self._mode_busy = False
        active = self.mode_engine.active
        self.modes_panel.set_active(active)
        card = active or previous or 'gaming'
        if error is not None:
            logging.getLogger(__name__).warning('mode_change_failed: %s', error)
            self.modes_panel.set_status(card, f'Could not change mode: {error}')
            return
        # The card has room for about three short facts; the tooltip keeps all of them.
        # After a switch, the old mode's "off" lines belong to the notification, not this card.
        facts = [line for line in lines if not (active and (line.endswith(' mode off')
                                                            or line.startswith('Unfroze')))]
        self._mode_lines[card] = (' · '.join(facts[:3]), '\n'.join(lines))
        self.modes_panel.set_status(card, *self._mode_lines[card])
        report, self._mode_report = self._mode_report, ''
        if report:
            self.modes_panel.set_status('gaming', 'Last match: ' + report)
            self.show_notification(APP_NAME, 'Match report', report)
        if active == 'gaming':
            self.gpu_sampler.start()
        title = f'{MODE_NAMES[active]} on' if active else (lines[0] if lines else 'Modes off')
        self.show_notification(APP_NAME, title, ' · '.join(lines[1:] if not active else lines))

    def _set_mode_auto(self, key, on):
        self.mode_settings[key] = bool(on)
        self.settings['modes'] = self.mode_settings
        self.save_settings()

    def choose_mode_apps(self):
        running = sorted({proc['name'] for proc in self.mode_engine.backend.user_processes()
                          if proc['name'].casefold().endswith('.exe')}, key=str.casefold)
        dialog = AppChooser(self.mode_settings, running, self)
        self.is_dialog_open = True
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            self.is_dialog_open = False
        if accepted:
            self.mode_settings = normalize_mode_settings(dialog.chosen())
            self.settings['modes'] = self.mode_settings
            self.save_settings()

    def _game_running(self):
        games = self._hidden_games()
        for proc in psutil.process_iter(['name']):
            if (proc.info.get('name') or '').casefold() in games:
                return True
        return False

    def tick_modes(self):
        now = time.time()
        try:
            battery = psutil.sensors_battery()
        except (OSError, RuntimeError, psutil.Error):
            battery = None
        plugged = bool(battery.power_plugged) if battery else True
        percent = battery.percent if battery else None
        self.battery_forecast.add(now, percent, plugged)
        if self._mode_busy:
            return
        active, settings = self.mode_engine.active, self.mode_settings
        changed = battery is not None and self._was_plugged is not None and plugged != self._was_plugged
        self._was_plugged = plugged if battery else None
        if changed and settings['auto_college']:
            if not plugged and active is None:
                return self.set_mode('college', auto=True)
            if plugged and active == 'college' and self.mode_engine.auto_started:
                return self.set_mode(None, auto=True)
        if settings['auto_gaming'] or (active == 'gaming' and self.mode_engine.auto_started):
            running = self._game_running()
            if running:
                self._game_seen_at = now
            else:
                self._game_auto_blocked = False
            if running and active is None and settings['auto_gaming'] and not self._game_auto_blocked:
                return self.set_mode('gaming', auto=True)
            if (not running and active == 'gaming' and self.mode_engine.auto_started
                    and now - self._game_seen_at > GAME_GRACE):
                return self.set_mode(None, auto=True)
        if active == 'college' and battery and not plugged:
            self._show_forecast(now, percent, battery.secsleft)

    def _show_forecast(self, now, percent, windows_secs):
        result = self.battery_forecast.empty_at(now, percent, windows_secs)
        if result is None:
            line = 'Learning how fast this battery drains…'
        else:
            empty, source = result
            line = f'10% battery at {clock_text(empty)} ({source})'
            clash = BatteryForecast.conflict(empty, self.settings.get('tasks', []),
                                             datetime.datetime.fromtimestamp(now))
            if clash:
                line += f', before {clash[1]} at {clock_text(clash[0])}'
                if self._forecast_warned != clash[1]:
                    self._forecast_warned = clash[1]
                    self.show_notification(APP_NAME, 'Battery will run low', line)
        summary, detail = self._mode_lines.get('college', ('', ''))
        self.modes_panel.set_status('college', (summary + '\n' if summary else '') + line,
                                    (detail + '\n' if detail else '') + line)

    def recover_modes(self):
        """At startup: undo a mode a crash or reboot left on."""
        left_on = self.mode_engine.active
        try:
            lines = self.mode_engine.recover()
        except OSError as error:
            lines = [f'Could not undo {MODE_NAMES.get(left_on, "the last mode")}: {error}']
        if left_on and lines:
            self.modes_panel.set_active(self.mode_engine.active)
            self.modes_panel.set_status(left_on, 'Restored after the last session: ' + ' · '.join(lines))
            self.show_notification(APP_NAME, 'Restored your settings', ' · '.join(lines))

    def shutdown_modes(self):
        """On every exit: stop sampling and undo the active mode. A failure leaves the journal for next start."""
        if not hasattr(self, 'mode_engine'):
            return
        self.mode_timer.stop()
        if self._mode_worker is not None:
            self._mode_worker.join(10)
        self.gpu_sampler.stop()
        try:
            self.mode_engine.deactivate()
        except OSError as error:
            logging.getLogger(__name__).warning('mode_restore_failed: %s', error)
