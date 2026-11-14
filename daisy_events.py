"""A tiny local channel for "an agent finished": one bounded JSON line, user-only pipe.

The Claude Code Stop hook sends {event: done}; Daisy's eyes feel proud. Nothing
here carries code, prompts or tool input, and nothing here can approve anything.
"""
import hashlib
import json
from pathlib import Path
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

MAX_EVENT = 2048
MIN_GAP = .4          # seconds between accepted events; a burst is one event
EVENTS = ('done',)
PROVIDERS = ('claude', 'codex')


def endpoint_name():
    digest = hashlib.sha256(str(Path.home()).casefold().encode()).hexdigest()[:24]
    return 'daisy-events-' + digest


def validate_event(value):
    """The only shape accepted; anything else is dropped."""
    if not isinstance(value, dict) or set(value) != {'version', 'event', 'provider', 'project'}:
        raise ValueError('Unsupported event')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported event version')
    if value['event'] not in EVENTS or value['provider'] not in PROVIDERS:
        raise ValueError('Unsupported event')
    project = value['project']
    if not isinstance(project, str) or len(project) > 120 or any(ord(c) < 32 for c in project):
        raise ValueError('Invalid project')
    return value


def make_event(event, provider, project=''):
    return validate_event(dict(version=1, event=event, provider=provider, project=str(project or '')[:120]))


def send_event(event, endpoint=None, timeout_ms=300):
    """Client side (the hook). True when Daisy accepted the line."""
    socket = QLocalSocket()
    try:
        socket.connectToServer(endpoint or endpoint_name())
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write((json.dumps(validate_event(event), separators=(',', ':')) + '\n').encode('ascii', 'replace'))
        socket.flush()
        return socket.waitForBytesWritten(timeout_ms)
    except (ValueError, OSError):
        return False
    finally:
        socket.disconnectFromServer()
        socket.abort()


class EventBridge(QObject):
    event_received = pyqtSignal(dict)

    def __init__(self, endpoint=None, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.endpoint = endpoint or endpoint_name()
        self.clock = clock
        self.error = ''
        self._last = -1e9
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.setMaxPendingConnections(8)
        self.server.newConnection.connect(self._accept)

    def start(self):
        if self.server.isListening():
            return True
        QLocalServer.removeServer(self.endpoint)  # a stale pipe from a crashed run
        if not self.server.listen(self.endpoint):
            self.error = 'The local event channel could not start.'
            return False
        return True

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            buffer = bytearray()
            socket.readyRead.connect(lambda s=socket, b=buffer: self._read(s, b))
            socket.disconnected.connect(socket.deleteLater)
            cutoff = QTimer(socket)   # owned by the socket, so it dies with it: no stale callback
            cutoff.setSingleShot(True)
            cutoff.timeout.connect(socket.abort)
            cutoff.start(1000)   # a client that never finishes is cut off
            self._read(socket, buffer)

    def _read(self, socket, buffer):
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > MAX_EVENT:
            socket.abort()
            return
        if b'\n' not in buffer:
            return
        line, _, rest = bytes(buffer).partition(b'\n')
        buffer.clear()
        try:
            event = validate_event(json.loads(line.decode('utf-8')))
        except (ValueError, UnicodeError, RecursionError):
            socket.abort()
            return
        socket.disconnectFromServer()
        now = self.clock()
        if now - self._last >= MIN_GAP:
            self._last = now
            self.event_received.emit(event)

    def close(self):
        self.server.close()
