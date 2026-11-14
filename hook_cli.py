"""`Daisy.exe --daisy-hook <kind>`: what Claude Code and Codex hooks run.

Kept tiny and free of the island's imports so a hook starts quickly. Both kinds
fail closed: with nothing decided, the agent keeps its own prompt.
"""
import os
import sys

from approval_protocol import MAX_FRAME, decode_frame

KINDS = ('claude-permission', 'codex-permission', 'claude-done')


def run_hook(kind, stdin=None, stdout=None):
    if kind not in KINDS:
        return 0
    if kind.endswith('-permission'):
        import permission_hook
        return permission_hook.main([kind.split('-')[0]], stdin, stdout)
    try:
        source = sys.stdin if stdin is None else stdin
        stream = getattr(source, 'buffer', source)
        payload = decode_frame(stream.read(MAX_FRAME + 1))
    except (ValueError, OSError, AttributeError):
        payload = {}
    cwd = payload.get('cwd') if isinstance(payload, dict) else ''
    project = os.path.basename(str(cwd or '').rstrip('\\/'))
    try:
        from PyQt6.QtCore import QCoreApplication
        import daisy_events
        QCoreApplication.instance() or QCoreApplication([])
        daisy_events.send_event(daisy_events.make_event('done', kind.split('-')[0], project))
    except (ValueError, OSError, RuntimeError):
        pass
    return 0   # a Stop hook prints nothing and never blocks the agent
