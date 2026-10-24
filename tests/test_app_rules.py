"""Foreground policies never confuse a cached process with its current window."""
import unittest
import psutil

from app_rules import ForegroundPolicy, RuleGuard, normalize_rules


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.current = [10, 1]
        self.names = {1: 'chrome.exe', 2: 'VALORANT-Win64-Shipping.exe', 3: 'editor.exe'}
        self.window_pids = {10: 1, 11: 1, 20: 2, 30: 3}
        self.restored = []
        self.reads = []
        def name(pid):
            self.reads.append(pid)
            return self.names[pid]
        self.policy = ForegroundPolicy(foreground=lambda: tuple(self.current),
            process_name=name, own_pid=99, clock=lambda: 0,
            is_window=lambda hwnd: hwnd in self.window_pids,
            window_pid=lambda hwnd: self.window_pids.get(hwnd),
            activate=self.restored.append)

    def test_defaults_overrides_and_exact_matching(self):
        self.assertEqual(self.policy.mode(), 'click')
        self.policy.set_rules({'CHROME.EXE': 'hover', 'editor.exe': 'hidden'})
        self.assertEqual(self.policy.mode(), 'hover')
        self.current[:] = [30, 3]
        self.assertTrue(RuleGuard(self.policy, 'hidden').is_active())
        self.names[3] = 'mychrome.exe'
        self.policy.set_rules({})
        self.assertEqual(self.policy.mode(), 'hover')
        self.current[:] = [20, 2]
        self.assertEqual(self.policy.mode(), 'hidden')

    def test_remembers_external_identity_but_refreshes_same_process_window(self):
        self.assertEqual(self.policy.mode(), 'click')
        self.current[:] = [11, 1]
        self.assertEqual(self.policy.mode(), 'click')
        self.current[:] = [90, 99]
        self.assertEqual(self.policy.mode(), 'click')
        self.policy.restore_focus()
        self.assertEqual(self.restored, [11])
        self.assertEqual(self.reads, [1])

    def test_never_steals_focus_or_targets_reused_window(self):
        self.policy.mode()
        self.current[:] = [30, 3]
        self.policy.restore_focus()
        self.assertEqual(self.restored, [])
        self.current[:] = [90, 99]
        self.window_pids[10] = 42
        self.policy.restore_focus()
        self.assertEqual(self.restored, [])

    def test_denied_or_missing_foreground_is_safe(self):
        self.current[:] = [40, 4]
        self.assertEqual(self.policy.mode(), 'hover')
        self.current[:] = [0, 0]
        self.assertEqual(self.policy.mode(), 'hover')

    def test_validation_rejects_paths_duplicates_and_bad_modes(self):
        self.assertEqual(normalize_rules({' BRAVE.EXE ': 'click'}), {'brave.exe': 'click'})
        for value in ([], {'': 'hover'}, {'foo': 'click'}, {'C:/foo.exe': 'hover'},
                      {'foo.exe': 'no'}, {'A.exe': 'hover', 'a.exe': 'click'},
                      {'a.exe\n': 'hover'}, {42: 'hidden'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_rules(value)

    def test_denied_process_clears_a_previous_hidden_identity(self):
        self.current[:] = [20, 2]
        self.assertEqual(self.policy.mode(), 'hidden')
        self.current[:] = [30, 3]
        self.policy.process_name = lambda _: (_ for _ in ()).throw(psutil.AccessDenied())
        self.assertEqual(self.policy.mode(), 'hover')
        self.current[:] = [90, 99]
        self.assertEqual(self.policy.mode(), 'hover')

    def test_invalid_constructor_rules_are_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            ForegroundPolicy([])
