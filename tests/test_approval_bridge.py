import json
import time
import unittest
import uuid

from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from approval_bridge import ApprovalBridge
from approval_protocol import encode_frame, decode_frame, MAX_FRAME


class ApprovalBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.now = 10.0
        self.bridge = ApprovalBridge('daisy-test-' + uuid.uuid4().hex,
                                     clock=lambda: self.now)
        self.assertTrue(self.bridge.start(), self.bridge.error)
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.abort()
        self.bridge.close()
        self.pump()

    def pump(self):
        for _ in range(15):
            self.app.processEvents()

    def wait_for(self, condition):
        deadline = time.monotonic() + 2
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.001)
        self.assertTrue(condition(), 'Windows pipe delivery did not settle')

    def connect(self, frame=None):
        client = QLocalSocket()
        client.connectToServer(self.bridge.endpoint)
        self.assertTrue(client.waitForConnected(1000))
        self.clients.append(client)
        self.pump()
        if frame is not None:
            client.write(frame)
            client.flush()
            self.pump()
        return client

    def payload(self, nonce=None):
        return dict(version=1, provider='claude', nonce=nonce or uuid.uuid4().hex,
                    session_id='session', cwd='X:/work', tool_name='Bash',
                    tool_input={'command': 'echo hello'})

    def test_private_concurrent_one_shot_decisions(self):
        a, b = self.payload(), self.payload()
        clients = [self.connect(encode_frame(v)) for v in (a, b)]
        self.wait_for(lambda: len(self.bridge.pending()) == 2)
        pending = self.bridge.pending()
        self.assertEqual(len(pending), 2)
        self.assertNotEqual(pending[0]['id'], pending[1]['id'])
        self.assertTrue(self.bridge.resolve(pending[0]['id'], 'allow'))
        self.assertFalse(self.bridge.resolve(pending[0]['id'], 'deny'))
        self.pump()
        self.wait_for(lambda: clients[0].bytesAvailable() > 0)
        self.assertEqual(decode_frame(bytes(clients[0].readAll()))['nonce'], a['nonce'])
        self.assertEqual(bytes(clients[1].readAll()), b'')
        self.assertEqual(len(self.bridge.pending()), 1)

    def test_expiry_checked_before_timer_and_disconnect_removed(self):
        client = self.connect(encode_frame(self.payload()))
        self.wait_for(lambda: len(self.bridge.pending()) == 1)
        request_id = self.bridge.pending()[0]['id']
        self.now = 131
        self.assertFalse(self.bridge.resolve(request_id, 'allow'))
        self.assertEqual(self.bridge.pending(), [])
        other = self.connect(encode_frame(self.payload()))
        self.wait_for(lambda: len(self.bridge.pending()) == 1)
        other.abort()
        self.pump()
        self.wait_for(lambda: not self.bridge.pending())
        self.assertEqual(self.bridge.pending(), [])
        self.assertEqual(bytes(client.readAll()), b'')

    def test_invalid_oversize_replayed_and_second_frames_cannot_allow(self):
        for raw in (b'{bad}\n', b'x' * (MAX_FRAME + 1),
                    b'{"version":1,"version":1}\n'):
            invalid = self.connect(raw)
            self.wait_for(lambda: invalid.state() == QLocalSocket.LocalSocketState.UnconnectedState)
            self.assertEqual(self.bridge.pending(), [])
        payload = self.payload()
        self.connect(encode_frame(payload))
        self.wait_for(lambda: len(self.bridge.pending()) == 1)
        self.connect(encode_frame(payload))
        self.wait_for(lambda: self.clients[-1].state() == QLocalSocket.LocalSocketState.UnconnectedState)
        self.assertEqual(len(self.bridge.pending()), 1)
        self.clients[-2].write(encode_frame(self.payload()))
        self.clients[-2].flush()
        self.pump()
        self.wait_for(lambda: not self.bridge.pending())
        self.assertEqual(self.bridge.pending(), [])

    def test_occupied_endpoint_and_shutdown(self):
        other = ApprovalBridge(self.bridge.endpoint)
        self.assertFalse(other.start())
        self.assertTrue(other.error)
        self.assertEqual(self.bridge.server.socketOptions(),
                         QLocalServer.SocketOption.UserAccessOption)
        client = self.connect(encode_frame(self.payload()))
        self.bridge.close()
        self.pump()
        self.assertEqual(self.bridge.pending(), [])
        self.assertEqual(bytes(client.readAll()), b'')

    def test_snapshot_does_not_mutate_pending_and_queue_bounded(self):
        for _ in range(21):
            self.connect(encode_frame(self.payload()))
        self.wait_for(lambda: len(self.bridge.pending()) == 20)
        self.assertEqual(len(self.bridge.pending()), 20)
        snapshot = self.bridge.pending()
        snapshot[0]['tool_input']['command'] = 'changed'
        self.assertEqual(self.bridge.pending()[0]['tool_input']['command'], 'echo hello')

    def test_fragmented_request_and_incomplete_client_deadline(self):
        raw = encode_frame(self.payload())
        client = self.connect(raw[:20])
        self.assertEqual(self.bridge.pending(), [])
        client.write(raw[20:])
        client.flush()
        self.pump()
        self.wait_for(lambda: len(self.bridge.pending()) == 1)
        self.assertEqual(len(self.bridge.pending()), 1)
        idle = self.connect(b'{')
        self.now += 3
        self.bridge._expire()
        # The pipe reports the server's abort asynchronously; wait for it rather than
        # assuming a fixed number of event-loop passes.
        self.wait_for(lambda: idle.state() == QLocalSocket.LocalSocketState.UnconnectedState)
        self.assertEqual(idle.state(), QLocalSocket.LocalSocketState.UnconnectedState)
        self.assertEqual(len(self.bridge.pending()), 1)


if __name__ == '__main__':
    unittest.main()
