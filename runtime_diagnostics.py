"""Bounded local failure diagnostics without user content or uploads.

Questions answered: did startup/restart fail, which exception and code location,
and was Qt reporting warnings? A session ID correlates events across threads.
Messages, source lines, locals, media and preference values are never serialized.
"""
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
import traceback
import uuid
import subprocess

from PyQt6.QtCore import QStandardPaths, QtMsgType, qInstallMessageHandler
from runtime_fatal import start_sink

LOG_BYTES = 1024 * 1024
_handler = None
_directory = None
_hooks = None
_fatal_enabled = False
_fatal_process = None
_session = ''
_EVENTS = {'startup_begin', 'startup_ready', 'startup_failed', 'shutdown_begin',
           'shutdown_complete', 'restart_requested', 'restart_launched', 'restart_failed',
           'startup_restore_failed', 'instance_already_running', 'qt_warning',
           'qt_critical', 'qt_fatal', 'uncaught_python', 'uncaught_thread',
           'fatal_capture_ready', 'fatal_capture_failed'}


class SafeFormatter(logging.Formatter):
    def format(self, record):
        # No interpolation: arbitrary logger messages may contain private content.
        event = record.msg if isinstance(record.msg, str) and record.msg in _EVENTS else 'runtime_event'
        data = {'time': self.formatTime(record), 'level': record.levelname,
                'session': _session, 'event': event,
                'location': f'{Path(record.pathname).name}:{record.funcName}:{record.lineno}'}
        if record.exc_info and record.exc_info[0]:
            data['exception'] = record.exc_info[0].__name__
            data['stack'] = [f'{Path(frame.filename).name}:{frame.name}:{frame.lineno}'
                             for frame in traceback.extract_tb(record.exc_info[2])[-12:]]
        # The fixed allowlisted fields and bounded stack keep a record under rotation size.
        rendered = json.dumps(data, ensure_ascii=True)
        if len(rendered.encode('utf-8')) >= LOG_BYTES - 1:
            data.pop('stack', None)
            rendered = json.dumps(data, ensure_ascii=True)
        return rendered


def _python_exception(kind, value, tb):
    logging.getLogger(__name__).critical('uncaught_python', exc_info=(kind, value, tb))


def _thread_exception(args):
    logging.getLogger(__name__).critical('uncaught_thread',
                                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def _qt_message(kind, context, message):
    events = {QtMsgType.QtWarningMsg: 'qt_warning', QtMsgType.QtCriticalMsg: 'qt_critical',
              QtMsgType.QtFatalMsg: 'qt_fatal'}
    if kind in events:
        # Qt text can include URL/content. Category and source location are not required
        # to identify the Qt severity, so the payload is deliberately excluded.
        logging.getLogger(__name__).log(logging.CRITICAL if kind == QtMsgType.QtFatalMsg
                                       else logging.WARNING, events[kind])


def configure_diagnostics():
    """Install process/thread/Qt hooks once, keeping three files of at most 1MB."""
    global _handler, _directory, _hooks, _session
    if _handler is not None:
        return _directory
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    _directory = base / 'logs'
    _directory.mkdir(parents=True, exist_ok=True)
    # Two regular files plus one independently capped crash.log. Remove only
    # the obsolete oldest file from the previous three-regular-log layout.
    (_directory / 'daisy.log.2').unlink(missing_ok=True)
    _session = uuid.uuid4().hex[:12]
    handler = RotatingFileHandler(_directory / 'daisy.log', maxBytes=LOG_BYTES,
                                 backupCount=1, encoding='utf-8')
    handler.setFormatter(SafeFormatter())
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    previous_level = root.level
    root.setLevel(min(root.level, logging.INFO))
    root.addHandler(handler)
    previous_qt = qInstallMessageHandler(_qt_message)
    _hooks = (sys.excepthook, threading.excepthook, previous_qt, previous_level)
    sys.excepthook = _python_exception
    threading.excepthook = _thread_exception
    _handler = handler
    logging.getLogger(__name__).info('startup_begin')
    return _directory


def enable_fatal_capture():
    """Call only after the instance lock succeeds; works with no native stderr."""
    global _fatal_process, _fatal_enabled
    if _fatal_enabled:
        return True
    if _handler is None:
        return False
    process = None
    try:
        process = start_sink(_directory)
        faulthandler.enable(file=process.stdin, all_threads=True)
        _fatal_process, _fatal_enabled = process, True
        logging.getLogger(__name__).info('fatal_capture_ready')
        return True
    except (OSError, ValueError, RuntimeError):
        if process is not None:
            _close_sink(process)
        logging.getLogger(__name__).exception('fatal_capture_failed')
        return False


def _close_sink(process):
    try:
        process.stdin.close()
    except (OSError, ValueError):
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
    except OSError:
        pass


def diagnostic_info():
    frozen = bool(getattr(sys, 'frozen', False))
    return {'version': '1.0.0', 'application_path': str(Path(sys.executable).resolve()
            if frozen else Path(__file__).resolve().with_name('main.py')),
            'runtime': 'Installed app' if frozen else 'Python source',
            'log_directory': str(_directory) if _directory is not None else 'Unavailable'}


def shutdown_diagnostics():
    """Release files/hooks for tests and orderly application teardown."""
    global _handler, _hooks, _fatal_enabled, _fatal_process
    if _handler is None:
        return
    if _fatal_enabled:
        faulthandler.disable()
        _fatal_enabled = False
    if _fatal_process is not None:
        _close_sink(_fatal_process)
        _fatal_process = None
    root = logging.getLogger()
    root.removeHandler(_handler)
    _handler.close()
    _handler = None
    if _hooks is not None:
        sys.excepthook, threading.excepthook, previous_qt, previous_level = _hooks
        qInstallMessageHandler(previous_qt)
        root.setLevel(previous_level)
        _hooks = None
