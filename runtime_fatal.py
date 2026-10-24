"""A separate bounded pipe sink that remains alive after Daisy's fatal exit.

No Qt, logger or instance lock is created in the sink process. Only Python's
faulthandler writes to this pipe: tracebacks contain code locations, not locals,
exception messages, media titles, preferences or task text.
"""
import os
from pathlib import Path
import subprocess
import sys

MAX_CRASH_BYTES = 1024 * 1024
SINK_FLAG = '--daisy-fatal-sink'


def is_sink_command(argv):
    return len(argv) == 3 and argv[1] == SINK_FLAG


def sink_command(path):
    command = [sys.executable]
    if not getattr(sys, 'frozen', False):
        command.append(str(Path(__file__).resolve()))
    return command + [SINK_FLAG, str(path)]


def start_sink(directory):
    """Start one isolated writer; caller retains stdin until orderly shutdown."""
    command = sink_command(Path(directory) / 'crash.log')
    return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, bufsize=0, shell=False,
                            cwd=str(Path(directory)),
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def copy_bounded(stream, destination, limit=MAX_CRASH_BYTES):
    """Preserve old evidence until the first byte; cap writes and drain to EOF.

    Draining even after reaching the bound (or a write error) prevents a blocked
    faulthandler from hanging a terminating application on a full pipe.
    """
    output, written, failed = None, 0, False
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            if failed or written >= limit:
                continue
            try:
                if output is None:
                    output = Path(destination).open('wb')
                clipped = chunk[:limit - written]
                output.write(clipped)
                output.flush()
                written += len(clipped)
            except OSError:
                failed = True
    except OSError:
        failed = True
    finally:
        if output is not None:
            try:
                output.close()
            except OSError:
                failed = True
    return int(failed)


def _stdin_binary():
    stream = getattr(sys.stdin, 'buffer', None)
    if stream is not None:
        return stream
    # PyInstaller --noconsole/pythonw sets sys.stdin=None even when a parent
    # supplies an inherited stdin pipe. Recover that explicit native handle.
    if os.name != 'nt':
        raise OSError('No inherited crash pipe')
    import ctypes
    from ctypes import wintypes
    import msvcrt
    native = ctypes.WinDLL('kernel32', use_last_error=True)
    native.GetStdHandle.argtypes = [wintypes.DWORD]
    native.GetStdHandle.restype = wintypes.HANDLE
    handle = native.GetStdHandle(wintypes.DWORD(-10))
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError('No inherited crash pipe')
    descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    return os.fdopen(descriptor, 'rb', buffering=0)


def run_sink_command(argv=None):
    argv = sys.argv if argv is None else argv
    if not is_sink_command(argv):
        return 2
    destination = Path(argv[2])
    if destination.name != 'crash.log' or not destination.parent.is_dir():
        return 2
    try:
        with _stdin_binary() as stream:
            return copy_bounded(stream, destination)
    except OSError:
        return 1


def run_sink():
    return run_sink_command()


if __name__ == '__main__':
    raise SystemExit(run_sink())
