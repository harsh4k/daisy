"""A flight recorder for the island's motion: the last seconds of every frame, kept in memory.

Glitches on a real desktop rarely reproduce in tests. When you see one, right-click →
"Save glitch report": the recent frames (size, position, state, window rectangle) and a
list of what looks wrong are written beside the logs. Nothing leaves the PC, and no
screen content is recorded: only Daisy's own numbers.
"""
from collections import deque
import json
import time

KEEP = 2400            # about 40 seconds at 60 frames a second
Y_JUMP = 3.0           # px the top edge may move in one frame
SIZE_JUMP = 160        # px the width may change in one frame
GAP_MS = 120           # a pause this long inside a running transition is a visible stutter

_frames = deque(maxlen=KEEP)


def record(window, event):
    """One line per geometry change, state change or overlay resize. Cheap: a tuple append."""
    layer = getattr(window, 'content_layer', None)
    _frames.append((time.perf_counter(), event, window._island_w, window._island_h,
                    getattr(window, '_island_y', None), window.current_state,
                    window.x(), window.y(), window.width(), window.height(),
                    round(layer.opacity(), 2) if layer is not None else 1.,
                    bool(layer.active) if layer is not None else False))


def clear():
    _frames.clear()


def frames():
    keys = ('t', 'event', 'w', 'h', 'y', 'state', 'win_x', 'win_y', 'win_w', 'win_h', 'opacity', 'snapshot')
    if not _frames:
        return []
    start = _frames[0][0]
    return [dict(zip(keys, (round((row[0] - start) * 1000, 1),) + row[1:])) for row in _frames]


def findings(rows):
    """Plain sentences about what looks wrong in a trace: jumps, off-centre frames, stutters."""
    found = []
    for a, b in zip(rows, rows[1:]):
        at = '%.0f ms' % b['t']
        moving = a['event'] == b['event'] == 'size'
        if a['y'] is not None and b['y'] is not None and abs(b['y'] - a['y']) > Y_JUMP:
            found.append(f"{at}: the top edge jumped {b['y'] - a['y']:+.1f} px in one frame ({a['state']} -> {b['state']})")
        if moving and abs(b['w'] - a['w']) > SIZE_JUMP:
            found.append(f"{at}: the width jumped {b['w'] - a['w']:+d} px in one frame")
        if moving and a['state'] == b['state'] and b['t'] - a['t'] > GAP_MS and (a['w'], a['h']) != (b['w'], b['h']):
            found.append(f"{at}: the animation froze for {b['t'] - a['t']:.0f} ms mid-transition")
        if b['w'] > b['win_w'] or b['h'] > b['win_h']:
            found.append(f"{at}: the island ({b['w']}x{b['h']}) was larger than its window ({b['win_w']}x{b['win_h']}): clipped")
        if (a['win_w'], a['win_x']) != (b['win_w'], b['win_x']):
            centre_a, centre_b = a['win_x'] + a['win_w'] / 2, b['win_x'] + b['win_w'] / 2
            if abs(centre_a - centre_b) > 1:
                found.append(f"{at}: the window's centre moved {centre_b - centre_a:+.1f} px: the island shifted sideways")
    return found


def save(window, directory):
    """Write the trace and a picture of Daisy itself; returns the report's path."""
    from pathlib import Path
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    rows = frames()
    screen = window.screen()
    report = dict(saved=stamp, findings=findings(rows), frames=rows,
                  style=window.island_style, reduced_motion=bool(getattr(window, 'reduced_motion', False)),
                  scale=screen.devicePixelRatio(), screen=[screen.geometry().width(), screen.geometry().height()],
                  screens=len(window.screen().virtualSiblings()))
    path = directory / f'glitch-{stamp}.json'
    path.write_text(json.dumps(report, indent=1), encoding='utf-8')
    window.grab().save(str(directory / f'glitch-{stamp}.png'))
    return path
