"""Event-loop-owned, user-only local permission request transport."""
import copy
import time
import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from approval_protocol import (MAX_FRAME, MAX_PENDING, REQUEST_TTL, decode_frame,
                               encode_frame, endpoint_name, validate_request)


class ApprovalBridge(QObject):
    changed = pyqtSignal()
    request_received = pyqtSignal(object)

    def __init__(self, endpoint=None, parent=None, clock=time.monotonic, ttl=REQUEST_TTL):
        super().__init__(parent)
        self.endpoint = endpoint or endpoint_name()
        self.error = ''
        self.clock = clock
        self.ttl = min(REQUEST_TTL, max(.01, ttl))
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.setMaxPendingConnections(MAX_PENDING)
        self.server.newConnection.connect(self._accept)
        self._clients = {}
        self._requests = {}
        self._nonces = {}
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._expire)

    def start(self):
        if self.server.isListening():
            return True
        probe = QLocalSocket()
        probe.connectToServer(self.endpoint)
        if probe.waitForConnected(100):
            probe.abort()
            self.error = 'Another approval bridge is already listening.'
            return False
        if not self.server.listen(self.endpoint):
            self.error = 'The local approval bridge could not start.'
            return False
        self.error = ''
        self.timer.start()
        return True

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if len(self._clients) >= MAX_PENDING:
                socket.abort()
                socket.deleteLater()
                continue
            self._clients[socket] = {'buffer': bytearray(), 'id': None,
                                     'deadline': self.clock() + 2}
            socket.setReadBufferSize(MAX_FRAME + 1)
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._drop(s))
            self._read(socket)

    def _read(self, socket):
        state = self._clients.get(socket)
        if state is None:
            return
        data = bytes(socket.readAll())
        if state['id'] and data:
            self._drop(socket)
            return
        state['buffer'].extend(data)
        raw = bytes(state['buffer'])
        if len(raw) > MAX_FRAME or (b'\n' in raw and not raw.endswith(b'\n')) or raw.count(b'\n') > 1:
            self._drop(socket)
            return
        if not raw.endswith(b'\n'):
            return
        try:
            request = validate_request(decode_frame(raw))
        except ValueError:
            self._drop(socket)
            return
        if request['nonce'] in self._nonces or len(self._nonces) >= 1000:
            self._drop(socket)
            return
        request_id = uuid.uuid4().hex
        expires = self.clock() + self.ttl
        self._nonces[request['nonce']] = expires + 120
        state.update(id=request_id, deadline=expires, nonce=request['nonce'])
        state['buffer'].clear()
        record = {key: request[key] for key in ('provider', 'session_id', 'cwd', 'tool_name', 'tool_input')}
        record.update(id=request_id, expires_at=expires)
        self._requests[request_id] = (record, socket)
        self.changed.emit()
        self.request_received.emit(copy.deepcopy(record))

    def pending(self):
        self._expire()
        return [copy.deepcopy(record) for record, _ in self._requests.values()]

    def resolve(self, request_id, decision):
        if decision not in ('allow', 'deny'):
            return False
        current = self._requests.get(request_id)
        if current is None:
            return False
        record, socket = current
        if self.clock() >= record['expires_at'] or socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            self._drop(socket)
            return False
        state = self._clients.pop(socket)
        del self._requests[request_id]
        socket.write(encode_frame(dict(version=1, nonce=state['nonce'], decision=decision)))
        socket.flush()
        socket.disconnectFromServer()
        socket.deleteLater()
        self.changed.emit()
        return True

    def _drop(self, socket):
        state = self._clients.pop(socket, None)
        if state is None:
            return
        changed = self._requests.pop(state['id'], None) is not None
        socket.abort()
        socket.deleteLater()
        if changed:
            self.changed.emit()

    def _expire(self):
        now = self.clock()
        for socket, state in list(self._clients.items()):
            if now >= state['deadline']:
                self._drop(socket)
        self._nonces = {nonce: deadline for nonce, deadline in self._nonces.items() if deadline > now}

    def close(self):
        self.timer.stop()
        self.server.close()
        for socket in list(self._clients):
            self._drop(socket)
        self._nonces.clear()
