"""Deterministic Daisy interaction inactivity policy; no timers or desktop input."""
import importlib.util
import unittest


class IdleBehaviorTests(unittest.TestCase):
    def policy(self, timeout=10):
        self.assertIsNotNone(importlib.util.find_spec('idle_behavior'),
                             'Daisy needs a standalone inactivity policy')
        from idle_behavior import IdleBehavior
        self.now = 100.0
        return IdleBehavior(timeout, clock=lambda: self.now)

    def test_hides_at_timeout_boundary_only(self):
        policy = self.policy()
        self.now += 9.999
        self.assertFalse(policy.tick(False, False, 'Idle'))
        self.now += .001
        self.assertTrue(policy.tick(False, False, 'Idle'))

    def test_passive_polling_does_not_restart_inactivity(self):
        policy = self.policy()
        for elapsed in range(1, 10):
            self.now = 100 + elapsed
            self.assertFalse(policy.tick(False, False, 'Idle'))
        self.now = 110
        self.assertTrue(policy.tick(False, False, 'Idle'))

    def test_pointer_and_protection_each_restart_full_delay(self):
        for pointer, protected in ((True, False), (False, True), (True, True)):
            with self.subTest(pointer=pointer, protected=protected):
                policy = self.policy()
                self.now += 100
                self.assertFalse(policy.tick(pointer, protected, 'Idle'))
                self.now += 9.999
                self.assertFalse(policy.tick(False, False, 'Idle'))
                self.now += .001
                self.assertTrue(policy.tick(False, False, 'Idle'))

    def test_nonidle_states_protect_and_restart_delay(self):
        for state in ('Hover', 'Hidden', 'Notify'):
            with self.subTest(state=state):
                policy = self.policy()
                self.now += 100
                self.assertFalse(policy.tick(False, False, state))
                self.now += 9
                self.assertFalse(policy.tick(False, False, 'Idle'))
                self.now += 1
                self.assertTrue(policy.tick(False, False, 'Idle'))

    def test_explicit_interaction_resets_deadline(self):
        policy = self.policy()
        self.now += 9
        policy.note_interaction()
        self.now += 9
        self.assertFalse(policy.tick(False, False, 'Idle'))
        self.now += 1
        self.assertTrue(policy.tick(False, False, 'Idle'))

    def test_off_never_hides_and_can_be_enabled(self):
        policy = self.policy(0)
        self.now += 10000
        self.assertEqual(policy.timeout, 0)
        self.assertFalse(policy.tick(False, False, 'Idle'))
        policy.set_timeout(5)
        self.now += 4.999
        self.assertFalse(policy.tick(False, False, 'Idle'))
        self.now += .001
        self.assertTrue(policy.tick(False, False, 'Idle'))

    def test_timeout_values_are_strict_and_reset_deadline(self):
        for value in (0, 5, 10, 30):
            with self.subTest(value=value):
                policy = self.policy(value)
                self.assertEqual(policy.timeout, value)
                self.now += 100
                policy.set_timeout(value)
                self.assertFalse(policy.tick(False, False, 'Idle'))
        for invalid in (None, True, False, 5.0, '10', -1, 1, 60, [], {}):
            with self.subTest(invalid=invalid):
                policy = self.policy(invalid)
                self.assertEqual(policy.timeout, 10)
                policy.set_timeout(0)
                policy.set_timeout(invalid)
                self.assertEqual(policy.timeout, 10)


if __name__ == '__main__':
    unittest.main()
