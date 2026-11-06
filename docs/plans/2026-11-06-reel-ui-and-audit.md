# Reel UI parity, hover-open fix and code audit

Branch: `feat/reel-ui-and-hover-fix`. Baseline: 317 tests green (offscreen), checkpoint
`2026-11-06T09-19-36-340` holds the pre-existing uncommitted work.

Reference: Instagram reel DfF_ipuSiDh (twocode.nl, 10.5 s). Frames inspected at
0, 1, 2, 3, 4, 5, 6, 6.2, 6.5, 7, 7.2, 7.3, 7.5, 7.7, 8, 9, 10 s. Daisy borrows the look,
not their assets, logo or name.

## Findings from the reference

| Reel state | What it shows |
|---|---|
| Rest | Black notch, concave top ears, ~16 px lower corners, two glowing "eyes" centred. |
| Status chip (1 s) | Notch widens: app tile left, level bars right, eyes stay centred. |
| Volume HUD (2-3 s) | Notch widens: speaker glyph left, thick white rounded slider right. |
| Agent chip (4-5 s) | Notch widens: sunburst + state ("Editing", "Done") left, timer right, eyes centred and tinted per state. |
| Open (6-7.5 s) | One spring from notch to ~640x300 with a single overshoot; eyes shrink to a header dot pair. |
| Home page | Header: eyes, "Thu 29 Oct 2026" grey + time white-bold, "..." right. Three equal cards (radius ~22): label top-left, ringed glyph top-right, huge bold title and one-line subtitle bottom-left. Card washes: blue (agent), red (music, artwork tile), purple (focus). Bottom bar: Home pill (grey fill, icon + label) then icon-only tabs, volume at far right. |

## Defects found by tracing the hover (`scratchpad/trace_hover.py`)

1. Interrupting line -> pill with Hover leaves `_island_y` at ~2.6 for the whole open, then
   snaps to 10 at `finish()` (7 px jump).
2. The squash applies from a half-open pill, so the island shrinks (118 -> 104 wide) then
   grows. Visible dip.
3. Line -> Hover in one tick: island jumps from y 0 to y 10 on frame one, and the squash drives
   height to 0, so the line vanishes before opening.
4. Content opacity restarts at 0.26 on interruption, so text flashes.

## Scope decision (2026-11-06)

Owner: "just change the notch, nothing else". Only phase 1 (motion fix, transparent snapshot) is kept.
The Home cards, tab bar, header and Music page built in phase 2 were reverted; the reel findings
above stay as reference. Phase 3 (audit) was not carried further.

## Phases

1. **Motion fix** (`shell_motion.py`, `ignite_motion.py`, `overlay_fit.py`): explicit start y for
   every transition, y blended in the spring branch, squash only from a settled pill, opacity
   continues from the current value. Tests in `tests/test_ignite_motion.py` and a trace test.
2. **Reel UI**: Home page of three washed cards plus bottom tab bar; header with date and time;
   notch status chips; volume HUD; spring and eyes tuned to the frames. Tests updated to the new
   composition. Compare to frames after each step; iterate to parity.
3. **Audit** (`improve` / `code-review` lenses): event loop and timers, win32 calls, threads in
   monitors, exception paths, config load/save, leaks on repeated open/close, uncommitted work.
   Fix real bugs with tests; list the rest.
4. **Verify**: full unittest, `verify.mjs`, built-exe smoke test only with owner approval
   (installed `X:\Apps\Daisy` is running and is not touched).
