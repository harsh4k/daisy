"""Approval cards with Allow/Deny, the agent-finished channel and the eyes' reactions."""
import json
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
import test_hover
import settle
import daisy_events
import approval_setup
import hook_cli
from notification_banner import NotificationBanner, summarize, ARM_MS
from test_approval_integration import BridgeFixture

APP = test_hover.APP
RECORD = dict(id='abc123', provider='claude', session_id='s', cwd='X:/p', tool_name='Bash',
              tool_input={'command': 'npm   test\n--silent'}, expires_at=1e12)


class SummaryTests(unittest.TestCase):
    def test_summary_is_one_short_plain_line(self):
        self.assertEqual(summarize(RECORD), 'Bash: npm test --silent')
        long = dict(RECORD, tool_input={'command': 'x' * 500})
        self.assertLessEqual(len(summarize(long)), 90)
        self.assertTrue(summarize(long).endswith('…'))
        self.assertEqual(summarize(dict(RECORD, tool_input={})), 'Bash')
        self.assertIn('"a"', summarize(dict(RECORD, tool_input={'a': 1})) or '"a"')


class BannerApprovalTests(unittest.TestCase):
    def banner(self):
        banner = NotificationBanner()
        banner.show()
        self.addCleanup(banner.deleteLater)
        return banner

    def test_buttons_wake_after_a_moment_and_answer_once(self):
        banner = self.banner()
        answers = []
        banner.approval_answered.connect(lambda i, d: answers.append((i, d)))
        banner.set_message('Claude', '', '')
        banner.set_approval(RECORD)
        self.assertTrue(banner.actions.isVisible())
        self.assertFalse(banner.allow.isEnabled(), 'not clickable the instant the card appears')
        banner.allow.click()
        self.assertEqual(answers, [], 'a click that early is ignored')
        QTest.qWait(ARM_MS + 150)
        self.assertTrue(banner.allow.isEnabled() and banner.deny.isEnabled())
        banner.allow.click()
        banner.allow.click()
        banner.deny.click()
        self.assertEqual(answers, [('abc123', 'allow')], 'one answer per request, never two')

    def test_the_card_names_what_is_asked_and_the_result_pops_in(self):
        banner = self.banner()
        banner.set_message('Claude', '', '')
        banner.set_approval(RECORD)
        self.assertEqual((banner.title.full_text, banner.message.full_text), ('Permission requested', 'Bash: npm test --silent'))
        banner.show_result('allow')
        self.assertEqual(banner.title.text(), 'Allowed')
        self.assertFalse(banner.actions.isVisible())
        QTest.qWait(400)
        banner.show_result('deny')
        self.assertEqual(banner.title.text(), 'Denied')

    def test_a_replaced_request_rearms_its_own_buttons(self):
        banner = self.banner()
        banner.set_message('Claude', '', '')
        banner.set_approval(RECORD)
        QTest.qWait(ARM_MS + 150)
        banner.set_approval(dict(RECORD, id='next'))
        self.assertFalse(banner.allow.isEnabled(), 'the new request must be seen before it can be answered')
        banner.set_approval(None)
        self.assertFalse(banner.actions.isVisible())


class WindowApprovalTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def open_window(self):
        w = self.window({'motion_mode': 'full'})
        bridge = BridgeFixture()
        w.attach_approval_bridge(bridge)
        return w, bridge

    def test_a_request_reaches_you_even_when_the_island_is_open(self):
        w, bridge = self.open_window()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        w._pointer_over = True
        bridge.records = [RECORD]
        bridge.request_received.emit(RECORD)
        self.assertEqual(w.current_state, 'Notify')
        self.assertEqual(w.daisy_eyes.emotion, 'alert', 'wide-eyed while it waits for you')
        self.assertTrue(w.settle if False else settle.settle_shell(w))
        self.assertTrue(w.notification_banner.actions.isVisible())

    def test_allow_and_deny_answer_that_request_and_the_eyes_react(self):
        for decision, mood in (('allow', 'happy'), ('deny', 'sad')):
            w, bridge = self.open_window()
            bridge.records = [RECORD]
            bridge.request_received.emit(RECORD)
            self.assertTrue(settle.settle_shell(w))
            QTest.qWait(ARM_MS + 150)
            (w.notification_banner.allow if decision == 'allow' else w.notification_banner.deny).click()
            self.assertEqual(bridge.answers, [('abc123', decision)])
            self.assertEqual(w.daisy_eyes.emotion, mood)
            self.assertEqual(w.notification_banner.title.text(), 'Allowed' if decision == 'allow' else 'Denied')

    def test_a_request_that_ends_dismisses_its_card_and_calms_the_eyes(self):
        w, bridge = self.open_window()
        bridge.records = [RECORD]
        bridge.request_received.emit(RECORD)
        self.assertTrue(settle.settle_shell(w))
        bridge.records = []
        bridge.changed.emit()
        self.assertNotEqual(w.daisy_eyes.emotion, 'alert')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Idle')

    def test_agent_done_makes_the_eyes_proud_and_wakes_a_hidden_pill(self):
        w, _ = self.open_window()
        w.change_state('Hidden')
        self.assertTrue(settle.settle_shell(w))
        w.on_agent_event(daisy_events.make_event('done', 'claude', 'daisy'))
        self.assertEqual(w.daisy_eyes.emotion, 'proud')
        self.assertEqual(w.current_state, 'Idle')

    def test_focus_timer_finishing_is_a_happy_moment(self):
        w = self.window({'motion_mode': 'full'})
        w.on_timer_completed()
        self.assertEqual(w.daisy_eyes.emotion, 'happy')

    def test_the_clock_sets_the_mood_at_night(self):
        w = self.window({'motion_mode': 'full'})
        fixed = test_hover.main.datetime.datetime(2026, 11, 14, 23, 30)
        with patch.object(test_hover.main.datetime, 'datetime') as clock:
            clock.now.return_value = fixed
            w.update_content()
        self.assertEqual(w.daisy_eyes.emotion, 'sleepy')


SENDER = '\n'.join([
    'import sys',
    'sys.path.insert(0, sys.argv[2])',
    'from PyQt6.QtCore import QCoreApplication',
    'app = QCoreApplication([])',
    'import daisy_events',
    "sys.exit(0 if daisy_events.send_event(daisy_events.make_event('done', 'claude', 'a'), sys.argv[1]) else 1)"])


def send_like_a_hook(endpoint):
    """A real separate process, as the hook is, while this test keeps the server's event loop running."""
    import subprocess, sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    child = subprocess.Popen([sys.executable, '-I', '-c', SENDER, endpoint, root])
    while child.poll() is None:
        QTest.qWait(20)
    return child.returncode == 0


class EventChannelTests(unittest.TestCase):
    def test_only_the_exact_event_shape_is_accepted(self):
        good = daisy_events.make_event('done', 'claude', 'daisy')
        self.assertEqual(daisy_events.validate_event(dict(good)), good)
        for bad in (dict(good, extra=1), dict(good, event='run'), dict(good, provider='x'), dict(good, version=2),
                    dict(good, project='a' * 121), dict(good, project='a\nb'), [], 'done'):
            with self.assertRaises(ValueError, msg=bad):
                daisy_events.validate_event(bad)

    def test_an_event_travels_through_the_local_pipe(self):
        endpoint = 'daisy-events-test-' + uuid.uuid4().hex
        bridge = daisy_events.EventBridge(endpoint)
        self.addCleanup(bridge.close)
        self.assertTrue(bridge.start())
        got = []
        bridge.event_received.connect(got.append)
        self.assertTrue(send_like_a_hook(endpoint))
        QTest.qWait(200)
        self.assertEqual(got, [daisy_events.make_event('done', 'claude', 'a')])

    def test_junk_and_bursts_are_dropped(self):
        from PyQt6.QtNetwork import QLocalSocket
        endpoint = 'daisy-events-test-' + uuid.uuid4().hex
        now = [0.]
        bridge = daisy_events.EventBridge(endpoint, clock=lambda: now[0])
        self.addCleanup(bridge.close)
        bridge.start()
        got = []
        bridge.event_received.connect(got.append)
        junk = QLocalSocket()
        junk.connectToServer(endpoint)
        junk.waitForConnected(500)
        junk.write(b'{"not":"valid"}\n')
        junk.flush()
        QTest.qWait(150)
        now[0] = 10.
        send_like_a_hook(endpoint)
        QTest.qWait(150)
        now[0] = 10.1
        send_like_a_hook(endpoint)   # inside the minimum gap
        QTest.qWait(150)
        self.assertEqual(len(got), 1)

    def test_the_stop_hook_sends_the_project_name_and_prints_nothing(self):
        import io
        sent = []
        payload = json.dumps({'cwd': 'X:\\Projects\\daisy', 'hook_event_name': 'Stop', 'transcript_path': 'secret'})
        with patch.object(daisy_events, 'send_event', lambda event, *a, **k: sent.append(event) or True):
            out = io.StringIO()
            with patch('sys.stdout', out):
                self.assertEqual(hook_cli.run_hook('claude-done', io.BytesIO(payload.encode())), 0)
        self.assertEqual(sent, [daisy_events.make_event('done', 'claude', 'daisy')])
        self.assertEqual(out.getvalue(), '')
        self.assertNotIn('secret', json.dumps(sent))

    def test_unknown_hook_kinds_do_nothing(self):
        self.assertEqual(hook_cli.run_hook('rm-rf'), 0)


class ConnectClaudeTests(unittest.TestCase):
    def test_both_hooks_are_added_with_a_backup_and_nothing_else_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = os.path.join(folder, 'Daisy.exe')
            open(exe, 'wb').close()
            target = os.path.join(folder, 'settings.json')
            original = {'model': 'x', 'hooks': {'PermissionRequest': [{'matcher': 'Bash', 'hooks': [
                {'type': 'command', 'command': 'other'}]}], 'Stop': [{'hooks': [{'type': 'command', 'command': 'mine'}]}]}}
            with open(target, 'w') as stream:
                json.dump(original, stream)
            backup = approval_setup.install_hooks(target, approval_setup.frozen_entries(exe))
            self.assertTrue(backup and os.path.exists(backup))
            with open(backup) as stream:
                self.assertEqual(json.load(stream), original)
            with open(target) as stream:
                updated = json.load(stream)
            self.assertEqual(updated['model'], 'x')
            commands = [h['command'] for event in ('PermissionRequest', 'Stop')
                        for group in updated['hooks'][event] for h in group['hooks']]
            self.assertIn('other', commands)
            self.assertIn('mine', commands)
            self.assertTrue(any('--daisy-hook claude-permission' in c for c in commands))
            self.assertTrue(any('--daisy-hook claude-done' in c for c in commands))
            self.assertIsNone(approval_setup.install_hooks(target, approval_setup.frozen_entries(exe)), 'running it twice changes nothing')

    def test_a_broken_settings_file_is_left_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, 'settings.json')
            with open(target, 'w') as stream:
                stream.write('{ not json')
            with self.assertRaises(ValueError):
                approval_setup.install_hooks(target, approval_setup.frozen_entries(os.path.join(folder, 'Daisy.exe')))
            with open(target) as stream:
                self.assertEqual(stream.read(), '{ not json')


if __name__ == '__main__':
    unittest.main()
