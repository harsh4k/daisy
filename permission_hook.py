"""Console-only command hook: no decision means keep the originating prompt."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import time
import uuid

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtNetwork import QLocalSocket
from approval_protocol import (MAX_FRAME, REQUEST_TTL, decode_frame, encode_frame,
                               endpoint_name, validate_request)


def make_request(payload, provider):
    if not isinstance(payload, dict) or payload.get('hook_event_name') != 'PermissionRequest':
        raise ValueError('PermissionRequest required')
    return validate_request(dict(version=1, provider=provider, nonce=uuid.uuid4().hex,
        session_id=payload.get('session_id'), cwd=payload.get('cwd'),
        tool_name=payload.get('tool_name'), tool_input=payload.get('tool_input')))


def server_is_trusted(descriptor):
    """Verify the actual connected server, not an untrusted endpoint claim."""
    if os.name != 'nt' or int(descriptor) < 0:
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetNamedPipeServerProcessId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    kernel.GetNamedPipeServerProcessId.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    pid = wintypes.ULONG()
    if not kernel.GetNamedPipeServerProcessId(wintypes.HANDLE(int(descriptor)), ctypes.byref(pid)):
        return False
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return False
    try:
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            return False
        expected = Path(__file__).resolve().parent / 'dist' / 'Daisy.exe'
        return os.path.normcase(os.path.realpath(path.value)) == os.path.normcase(os.path.realpath(expected))
    finally:
        kernel.CloseHandle(handle)


def request_decision(payload, provider, endpoint=None, timeout=REQUEST_TTL, peer_check=None):
    request = make_request(payload, provider)
    app = QCoreApplication.instance() or QCoreApplication([])
    socket = QLocalSocket()
    try:
        socket.connectToServer(endpoint or endpoint_name())
        if not socket.waitForConnected(250):
            return None
        if not (peer_check or server_is_trusted)(socket.socketDescriptor()):
            return None
        socket.setReadBufferSize(MAX_FRAME + 1)
        socket.write(encode_frame(request))
        socket.flush()
        expires = time.monotonic() + min(REQUEST_TTL, max(0, timeout))
        data = bytearray()
        while time.monotonic() < expires:
            if not socket.bytesAvailable():
                socket.waitForReadyRead(min(250, max(1, int((expires - time.monotonic()) * 1000))))
            data.extend(bytes(socket.readAll()))
            if len(data) > MAX_FRAME:
                return None
            if b'\n' in data:
                response = decode_frame(bytes(data))
                if (set(response) != {'version', 'nonce', 'decision'}
                        or type(response['version']) is not int or response['version'] != 1
                        or response['nonce'] != request['nonce']
                        or response['decision'] not in ('allow', 'deny')):
                    return None
                return response['decision']
            if socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
                return None
        return None
    except (ValueError, OSError, OverflowError, RuntimeError):
        return None
    finally:
        socket.abort()


def main(argv=None, stdin=None, stdout=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in ('codex', 'claude'):
        return 0
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    try:
        stream = getattr(stdin, 'buffer', stdin)
        raw = stream.read(MAX_FRAME + 1)
        payload = decode_frame(raw.encode('utf-8') if isinstance(raw, str) else raw)
        make_request(payload, argv[0])
        decision = request_decision(payload, argv[0])
        if decision not in ('allow', 'deny'):
            return 0
        result = {'behavior': decision}
        if decision == 'deny':
            result['message'] = 'Denied in Daisy.'
        stdout.write(encode_frame({'hookSpecificOutput': {
            'hookEventName': 'PermissionRequest', 'decision': result}}).decode('ascii'))
        stdout.flush()
    except (ValueError, OSError, AttributeError, UnicodeError, RuntimeError):
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
