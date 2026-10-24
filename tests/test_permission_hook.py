import io
import json
import unittest
import uuid
import subprocess
import sys
from unittest.mock import patch

import permission_hook as hook
from approval_protocol import decode_frame, validate_request


class PermissionHookTests(unittest.TestCase):
    def payload(self):
        return {'hook_event_name': 'PermissionRequest', 'session_id': 'one',
                'cwd': 'X:/work', 'tool_name': 'Bash',
                'tool_input': {'command': 'echo hi'}, 'transcript_path': 'secret'}

    def test_exact_input_and_no_unnecessary_transcript(self):
        request = hook.make_request(self.payload(), 'codex')
        self.assertEqual(request['tool_input'], self.payload()['tool_input'])
        self.assertNotIn('transcript_path', request)
        self.assertEqual(request['provider'], 'codex')
        self.assertNotEqual(request['nonce'], hook.make_request(self.payload(), 'codex')['nonce'])
        validate_request(request)

    def test_only_permission_request_and_known_provider(self):
        for value in ({}, {**self.payload(), 'hook_event_name': 'PreToolUse'},
                      {**self.payload(), 'tool_input': 'bad'}):
            with self.assertRaises(ValueError):
                hook.make_request(value, 'claude')
        with self.assertRaises(ValueError):
            hook.make_request(self.payload(), 'unknown')

    def test_only_explicit_decision_has_stdout_and_no_policy_changes(self):
        for provider in ('codex', 'claude'):
            for decision in ('allow', 'deny', None):
                output = io.StringIO()
                with patch.object(hook, 'request_decision', return_value=decision):
                    self.assertEqual(hook.main([provider], io.StringIO(json.dumps(self.payload())), output), 0)
                if decision is None:
                    self.assertEqual(output.getvalue(), '')
                else:
                    body = json.loads(output.getvalue())['hookSpecificOutput']
                    self.assertEqual(body['decision']['behavior'], decision)
                    self.assertNotIn('updatedInput', body['decision'])
                    self.assertNotIn('updatedPermissions', body['decision'])

    def test_malformed_or_large_stdin_never_calls_bridge(self):
        for value in ('{bad}', 'x' * 70000,
                      '{"hook_event_name":"PermissionRequest","hook_event_name":"PreToolUse"}'):
            with patch.object(hook, 'request_decision') as request:
                output = io.StringIO()
                hook.main(['claude'], io.StringIO(value), output)
                request.assert_not_called()
                self.assertEqual(output.getvalue(), '')

    def test_untrusted_or_unavailable_peer_falls_back(self):
        self.assertFalse(hook.server_is_trusted(-1))
        self.assertIsNone(hook.request_decision(self.payload(), 'claude',
                                               endpoint='not-a-daisy-endpoint', timeout=.01))

    def test_rejects_nonfinite_and_duplicate_json(self):
        for raw in (b'{"v":NaN}\n', b'{"v":1,"v":2}\n', b'{"v":1e999}\n'):
            with self.assertRaises(ValueError):
                decode_frame(raw)

    def test_real_python_pipe_cannot_impersonate_installed_daisy(self):
        from PyQt6.QtWidgets import QApplication
        from approval_bridge import ApprovalBridge
        app = QApplication.instance() or QApplication([])
        bridge = ApprovalBridge('daisy-untrusted-' + uuid.uuid4().hex)
        self.assertTrue(bridge.start(), bridge.error)
        try:
            self.assertIsNone(hook.request_decision(self.payload(), 'claude',
                                                   endpoint=bridge.endpoint, timeout=.01))
            app.processEvents()
            self.assertEqual(bridge.pending(), [])
        finally:
            bridge.close()

    def test_actual_utf8_bytes_preserve_non_ascii_input(self):
        payload = self.payload()
        payload['tool_input'] = {'command': 'echo मुंबई 🌸'}
        stream = io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode('utf-8')),
                                  encoding='cp1252')
        with patch.object(hook, 'request_decision', return_value=None) as request:
            hook.main(['claude'], stream, io.StringIO())
            self.assertEqual(request.call_args.args[0]['tool_input'], payload['tool_input'])

    def test_real_private_round_trip_allow_and_deny(self):
        code = '''
import sys
from PyQt6.QtCore import QCoreApplication,QTimer
from approval_bridge import ApprovalBridge
app=QCoreApplication([])
bridge=ApprovalBridge(sys.argv[1])
if not bridge.start(): raise SystemExit(2)
bridge.request_received.connect(lambda record: bridge.resolve(record['id'],sys.argv[2]))
print('ready',flush=True)
QTimer.singleShot(10000,app.quit)
app.exec()
bridge.close()
'''
        for decision in ('allow', 'deny'):
            endpoint = 'daisy-roundtrip-' + uuid.uuid4().hex
            child = subprocess.Popen([sys.executable, '-c', code, endpoint, decision],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                result = hook.request_decision(self.payload(), 'claude', endpoint=endpoint,
                                               timeout=2, peer_check=lambda _: True)
                self.assertEqual(result, decision)
            finally:
                child.terminate()
                child.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
