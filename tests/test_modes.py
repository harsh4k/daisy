"""Gaming and College modes: every change is journaled first and undone exactly, even after a crash."""
import datetime
import json
import os
import tempfile
import unittest

from mode_engine import BALANCED, HIGH_PERFORMANCE, ModeEngine, normalize_mode_settings, with_power_saving
from mode_insights import BatteryForecast, MatchStats, parse_sample


class FakeBackend:
    own_pid = 1

    def __init__(self):
        self.scheme = HIGH_PERFORMANCE
        self.suspended = {}
        self.prefs = {r'C:\Apps\brave.exe': 'SwapEffectUpgradeEnable=1;'}
        self.processes = [
            {'pid': 10, 'name': 'ChatGPT.exe', 'create_time': 5.0, 'exe': r'C:\Apps\ChatGPT.exe'},
            {'pid': 11, 'name': 'ChatGPT.exe', 'create_time': 6.0, 'exe': r'C:\Apps\ChatGPT.exe'},
            {'pid': 12, 'name': 'Discord.exe', 'create_time': 7.0, 'exe': r'C:\Apps\Discord.exe'},
            {'pid': 13, 'name': 'brave.exe', 'create_time': 8.0, 'exe': r'C:\Apps\brave.exe'},
            {'pid': 14, 'name': 'Locked.exe', 'create_time': 9.0, 'exe': r'C:\Apps\Locked.exe'},
            {'pid': 15, 'name': 'Focused.exe', 'create_time': 9.5, 'exe': r'C:\Apps\Focused.exe'},
        ]
        self.foreground = 15
        self.loaded = [('qwen3.5:9b', 5 * 1024 ** 3)]

    def foreground_pid(self):
        return self.foreground

    def user_processes(self):
        return list(self.processes)

    def process_matches(self, pid, create_time):
        return any(p['pid'] == pid and p['create_time'] == create_time for p in self.processes)

    def suspend(self, pid):
        if pid == 14:
            return False
        self.suspended[pid] = self.suspended.get(pid, 0) + 1
        return True

    def resume(self, pid):
        self.suspended[pid] -= 1
        return True

    def get_power_scheme(self):
        return self.scheme

    def set_power_scheme(self, scheme):
        self.scheme = scheme
        return True

    def get_gpu_pref(self, path):
        return self.prefs.get(path)

    def set_gpu_pref(self, path, value):
        if value is None:
            self.prefs.pop(path, None)
        else:
            self.prefs[path] = value
        return True

    def unload_ollama(self):
        unloaded, self.loaded = self.loaded, []
        return unloaded

    def nvidia_apps(self):
        return ['Discord.exe']

    screen_nvidia = False

    def screen_on_nvidia(self):
        return self.screen_nvidia


SETTINGS = {'gaming_freeze': ['ChatGPT.exe', 'Discord.exe', 'Locked.exe', 'Focused.exe', 'Game.exe'],
            'college_freeze': ['ChatGPT.exe'],
            'college_gpu_saving': ['brave.exe', 'Discord.exe']}


class ModeEngineTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.journal = os.path.join(folder.name, 'mode_state.json')
        self.backend = FakeBackend()
        self.engine = ModeEngine(self.backend, self.journal, clock=lambda: 100.0)

    def test_gaming_freezes_only_safe_apps_and_undoes_everything(self):
        lines = self.engine.activate('gaming', SETTINGS, protected=['game.exe'])
        self.assertEqual(self.engine.active, 'gaming')
        self.assertEqual(self.backend.suspended, {10: 1, 11: 1}, 'Discord, the focused app and games stay live')
        self.assertIn('Unloaded qwen3.5:9b (5.0 GB of GPU memory)', lines)
        self.assertTrue(any('could not freeze Locked.exe' in line for line in lines))
        self.assertTrue(os.path.exists(self.journal))
        off = self.engine.deactivate()
        self.assertEqual(off[0], 'Gaming mode off')
        self.assertEqual(self.backend.suspended, {10: 0, 11: 0})
        self.assertEqual(self.backend.scheme, HIGH_PERFORMANCE)
        self.assertFalse(os.path.exists(self.journal))
        self.assertEqual(self.engine.deactivate(), [], 'Turning off twice changes nothing')

    def test_college_sets_balanced_and_intel_gpu_then_restores_exact_values(self):
        lines = self.engine.activate('college', SETTINGS)
        self.assertEqual(self.backend.scheme, BALANCED)
        self.assertEqual(self.backend.prefs[r'C:\Apps\brave.exe'], 'SwapEffectUpgradeEnable=1;GpuPreference=1;')
        self.assertEqual(self.backend.prefs[r'C:\Apps\Discord.exe'], 'GpuPreference=1;')
        self.assertIn('Still on the NVIDIA GPU: Discord.exe', lines)
        self.assertFalse(any('Optimus' in line for line in lines))
        self.engine.deactivate()
        self.backend.screen_nvidia = True
        self.assertTrue(any('Optimus' in line for line in self.engine.activate('college', SETTINGS)),
                        'A screen wired to the NVIDIA GPU is called out, since that GPU can never sleep')
        self.engine.deactivate()
        self.assertEqual(self.backend.scheme, HIGH_PERFORMANCE)
        self.assertEqual(self.backend.prefs, {r'C:\Apps\brave.exe': 'SwapEffectUpgradeEnable=1;'},
                         'An added preference is removed and an existing one is put back')

    def test_crash_journal_is_undone_on_next_start(self):
        self.engine.activate('college', SETTINGS)
        with open(self.journal) as stream:
            self.assertEqual(json.load(stream)['power_prev'], HIGH_PERFORMANCE)
        reborn = ModeEngine(self.backend, self.journal)
        self.assertEqual(reborn.active, 'college')
        self.assertEqual(reborn.recover()[0], 'College mode off')
        self.assertEqual(self.backend.suspended, {10: 0, 11: 0})
        self.assertEqual(self.backend.scheme, HIGH_PERFORMANCE)

    def test_restarted_process_with_reused_pid_is_not_touched(self):
        self.engine.activate('gaming', SETTINGS)
        self.backend.processes[0] = dict(self.backend.processes[0], create_time=50.0)
        self.backend.suspended[10] = 0
        self.engine.deactivate()
        self.assertEqual(self.backend.suspended[10], 0)

    def test_switching_modes_undoes_the_first(self):
        self.engine.activate('gaming', SETTINGS)
        lines = self.engine.activate('college', SETTINGS)
        self.assertEqual(lines[0], 'Gaming mode off')
        self.assertEqual(self.engine.active, 'college')
        self.engine.deactivate()
        self.assertEqual(self.backend.scheme, HIGH_PERFORMANCE)

    def test_settings_normalize(self):
        clean = normalize_mode_settings({'gaming_freeze': ['a.exe', 'A.EXE', r'C:\x.exe', 3, 'b.txt'],
                                         'auto_gaming': 'yes'})
        self.assertEqual(clean['gaming_freeze'], ['a.exe'])
        self.assertFalse(clean['auto_gaming'])
        self.assertEqual(normalize_mode_settings(None)['college_freeze'], ['ChatGPT.exe'])
        self.assertEqual(with_power_saving('GpuPreference=2;'), 'GpuPreference=1;')


class InsightTests(unittest.TestCase):
    def test_match_report_counts_heat_slowdown(self):
        stats = MatchStats(started=0)
        for line in ('70, 90, Not Active, Not Active, Not Active',
                     '83.91, 98, Active, Not Active, Not Active',
                     '[N/A], 1, Not Active, Not Active, Not Active'):
            sample = parse_sample(line)
            if sample:
                stats.add(sample)
        for _ in range(11):
            stats.add(parse_sample('80, 95, Not Active, Active, Active'))
        report = stats.report(ended=40 * 60)
        self.assertIn('40 min', report)
        self.assertIn('peak 84°C', report)
        self.assertIn('slowed by heat 1 min', report)
        self.assertIn('power-capped 1 min', report)
        self.assertEqual(MatchStats(0).report(60), '1 min · no GPU readings')
        brief = MatchStats(started=0)
        brief.add(parse_sample('70, 50, Active, Not Active, Active'))
        self.assertIn('slowed by heat under 1 min · power-capped under 1 min', brief.report(60))

    def test_sampler_thread_collects_and_stops(self):
        from mode_insights import GpuSampler
        now = [0.0]
        sampler = GpuSampler(clock=lambda: now[0], interval=0.01,
                             query=lambda: parse_sample('75, 80, Not Active, Not Active, Not Active'))
        self.assertEqual(sampler.stop(), '', 'Stopping before starting reports nothing')
        sampler.start()
        import time
        time.sleep(0.1)
        now[0] = 600
        self.assertIn('peak 75°C', sampler.stop())
        self.assertFalse(sampler._thread.is_alive())

    def test_forecast_measures_drain_and_flags_a_task(self):
        forecast = BatteryForecast()
        start = datetime.datetime(2026, 11, 16, 9, 0).timestamp()
        forecast.add(start, 80, plugged=False)
        forecast.add(start + 600, 75, plugged=False)
        empty, source = forecast.empty_at(start + 600, 75)
        self.assertEqual(source, 'measured')
        self.assertEqual(empty.strftime('%H:%M'), '11:20', '5% per 10 min: 65% more lasts 130 min')
        now = datetime.datetime.fromtimestamp(start + 600)
        tasks = [{'name': 'Lab', 'time': '10:30 AM'}, {'name': 'DSA lecture', 'time': '2:00 PM'}]
        self.assertEqual(BatteryForecast.conflict(empty, tasks, now)[1], 'DSA lecture')
        forecast.add(start + 700, 74, plugged=True)
        self.assertIsNone(forecast.empty_at(start + 700, 74), 'Plugging in forgets the old drain')
        self.assertEqual(forecast.empty_at(start, 50, windows_secs=3600)[1], 'Windows estimate')


class ModesTabTests(unittest.TestCase):
    def window(self, config):
        import test_hover
        return test_hover.HoverTests.window(self, config)

    def wait_idle(self, w):
        from PyQt6.QtTest import QTest
        for _ in range(100):
            if not w._mode_busy:
                return
            QTest.qWait(20)
        self.fail('Mode change never finished')

    def test_tab_switches_with_fake_system_and_saves_auto_choice(self):
        from types import SimpleNamespace
        w = self.window({})
        tabs = w.tools_panel.tabs
        self.assertIn('Modes', [tabs.tabText(i) for i in range(tabs.count())])
        self.assertIsNone(w.mode_engine.active, 'Building the island changes nothing on the PC')
        w.mode_engine.backend = FakeBackend()
        sampler = SimpleNamespace(started=0, start=lambda: setattr(sampler, 'started', 1),
                                  stop=lambda: '12 min · peak 70°C')
        w.gpu_sampler = sampler
        w.modes_panel.cards['gaming'].switch.click()
        self.wait_idle(w)
        self.assertEqual(w.mode_engine.active, 'gaming')
        self.assertEqual(sampler.started, 1)
        self.assertTrue(w.modes_panel.cards['gaming'].switch.isChecked())
        w.modes_panel.cards['college'].switch.click()
        self.wait_idle(w)
        self.assertEqual(w.mode_engine.active, 'college')
        self.assertIn('Last match: 12 min', w.modes_panel.cards['gaming'].status.text())
        self.assertNotIn('Gaming mode off', w.modes_panel.cards['college'].status.text())
        self.assertIn('Balanced power plan', w.modes_panel.cards['college'].status.text())
        w.modes_panel.cards['college'].auto.setChecked(True)
        with open(w.config_path) as stream:
            self.assertTrue(json.load(stream)['modes']['auto_college'])
        w.close()
        self.assertIsNone(w.mode_engine.active, 'Closing Daisy undoes the mode')
        self.assertEqual(w.mode_engine.backend.scheme, HIGH_PERFORMANCE)

    def test_auto_start_follows_charger_and_game(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import mode_wiring
        w = self.window({'modes': {'auto_college': True, 'auto_gaming': True}})
        w.mode_timer.stop()
        w.mode_engine.backend = FakeBackend()
        w.gpu_sampler = SimpleNamespace(start=lambda: None, stop=lambda: '')
        battery = SimpleNamespace(percent=80, power_plugged=True, secsleft=-2)
        game = [False]
        w._game_running = lambda: game[0]

        def tick():
            with patch.object(mode_wiring.psutil, 'sensors_battery', return_value=battery):
                w.tick_modes()
            self.wait_idle(w)

        tick()
        self.assertIsNone(w.mode_engine.active)
        battery.power_plugged = False
        tick()
        self.assertEqual(w.mode_engine.active, 'college', 'Unplugging starts College mode')
        battery.power_plugged = True
        tick()
        self.assertIsNone(w.mode_engine.active, 'Plugging in ends an auto-started College mode')
        game[0] = True
        tick()
        self.assertEqual(w.mode_engine.active, 'gaming', 'A running game starts Gaming mode')
        w.set_mode(None)
        self.wait_idle(w)
        tick()
        self.assertIsNone(w.mode_engine.active, 'Turning it off by hand sticks while the game runs')
        game[0] = False
        tick()
        game[0] = True
        tick()
        self.assertEqual(w.mode_engine.active, 'gaming', 'The next game session starts it again')
        game[0] = False
        w._game_seen_at -= mode_wiring.GAME_GRACE + 1
        tick()
        self.assertIsNone(w.mode_engine.active, 'Closing the game ends an auto-started Gaming mode')


if __name__ == '__main__':
    unittest.main()
