# Daisy design

## Intent and reference

Daisy is a quiet Windows companion: glance at time, media and system activity,
then deliberately expand it for useful controls. The supplied Mac screenshot is
a reference for a third-party notch application, not an Apple Dynamic Island
specification. Borrow its clear grouping, black foundation, media emphasis and
coordinated movement while retaining Daisy's Windows behavior.

Earlier versions felt like a small dashboard: competing labels, large tinted
surfaces, too many outlined controls and transitions that exposed layout changes.
Previously reported defects include drifting hover text, off-center compact
content, duplicate provider logos, notification flicker, detached desktop-sized
window outlines and interference with browser tabs and games. These are explicit
regression cases, not acceptable tradeoffs for the new appearance.

## Visual system

- Font: bundled Inter Variable under the SIL Open Font License, falling back to
  Segoe UI Variable then Segoe UI. SF Pro is not installed and Apple's published
  license does not permit embedding it in this Windows app. This is an explicitly
  disclosed visual substitute, not an identical copy of Apple's system typography.
- Roles follow macOS text styles in logical pixels: display 32/600 (timer),
  section 17/600 (Title 2), title 13/600 (Headline), body 13/400, secondary
  12/400 (Callout), time and caption 11/400 (Footnote). The pill clock uses
  13/600. Text at 17 px and above is tightened like SF (-0.25 px at 17, -0.6 at 32).
- Enable tabular numerals and verify actual digit advances; use a stable numeric
  fallback if the selected font cannot provide them. Elision recomputes after
  font/style changes. Long titles expose full tooltips and never scroll on hover.
- The island is true black (`island` token) so it merges with a notch or the
  screen edge; tinted themes keep their coloured shell. Theme selection changes
  restrained accents. Notifications use the light porcelain material
  (`porcelain_*` tokens): warm white card, near-black label, Apple's secondary
  and tertiary greys, one hairline edge, a top highlight and a soft shadow.
- White primary text, grey secondary text, semantic danger feedback. Every color
  belongs to theme tokens; publisher logos keep their original colors.
- macOS rhythm on a four-pixel grid: edge insets 20, groups 16, card insets 12,
  controls 8, related text 4. Nested corners are concentric (inner radius =
  outer radius - inset); the expanded island and notch cap at 28, cards use 20.
- Utility icons20, transport24, play/pause32; interactive targets at least32.
  Use one Phosphor icon family for navigation, transport and utility actions;
  preserve original provider logos and Windows file icons.
  Separate groups with space and tonal surfaces. Routine buttons have no border;
  form boundaries and visible keyboard-focus indicators remain.
- Aim for WCAG AA contrast:4.5:1 ordinary text,3:1 large text and essential
  control/focus indicators. Disabled controls remain recognizably unavailable.

## Composition, icons and writing

The open island follows **Stage**, chosen from the island studies: there is no
dock. A 44 px top bar holds a crumb on the left ("Now" at home, "‹ Now" on any
other page) and the battery, time and Power menu on the right. The Now page puts
music first (96 px artwork with concentric 18 px corners, eyebrow, title,
artist, scrubber, transport) and four glances beside it: Focus, the next task,
today's date and the weather. Each glance opens its page; the crumb returns.
Every page brings its own light behind its content (`stage_wash.py`): the album
colour or accent on Now, sky and sun on Weather, a faint accent on Tasks, night
blue on Calendar and amber on Tools, crossfading over 320 ms when the page
changes. Weather shows an 84 px thin temperature beside a sunlit curve of the
next hours; Calendar shows today as a 76 px thin numeral with the day's agenda
beside a painted month that rings today. CPU, memory, disk, network and battery
detail live in Tools → System. Keep artwork square with a consistent crop,
exactly one original provider mark when artwork is missing, and stable feedback
space for transport results. Capability-aware transport and seeking remain
unchanged. Focus rings appear for keyboard focus only, as on macOS.

Use sentence case and short natural labels. Explain unfamiliar or consequential
actions; remove labels that merely repeat surrounding content. Familiar playback,
close and settings controls can be icon-only with accessible names and tooltips.
Navigation is the crumb and the glances; scrolling inside the island still
moves through pages, and every entry point keeps a tooltip and accessible name.
Tools tabs mark the current tab with an accent underline instead of a fill.
One Power menu exposes Sleep, Restart PC
and Shut down; retain existing confirmation behavior. Restart Daisy is a separate
recovery action. Never execute real power actions in verification.

Apply the same roles to Weather, Tasks, Calendar, Tools, Settings and notifications.
All expanded feature shells use Overview's 624 by 272 logical-pixel size, clamped
to the available screen. Navigation stays fixed below a vertical scrolling
content viewport. Long task lists, the task editor and Tools remain reachable
without shrinking controls or changing the shell when switching features.
Scrollbars remain visually hidden; wheel, touchpad and keyboard scrolling stay
available, and focused form fields scroll into view.
Each page uses the full content width. Weather distributes forecasts across it;
Calendar uses a readable seven-column numbered day grid; Tasks uses aligned rows
and a two-column editor; Tools puts its timer and actions side by side. Default
controls fit the content height; only genuinely long lists need scrolling.
The pill follows the Dynamic Island compact layout: a 22 px leading slot, the
centred clock, and a mirrored 22 px trailing slot. The leading slot holds the
Aurora orb (a small glass sphere whose three lights drift on a 12 s loop, drawn
from cached frames at 20 fps only while visible); the trailing slot shows audio
bars while music plays. Both glow in the album colour while music plays and in
the theme accent otherwise. The notch has 8 px concave ears at the screen edge
and lower corners that grow with height (12 px for the pill, up to 28).

A notification swells the pill into a sender chip (icon and name in the same
slots) and drops a porcelain card 8 px below it: 400 px wide, 38 px app icon,
sender and time, title, message, a 32 px dismiss and an optional Review pill.
Hovering the card holds it; leaving resumes a 2 s timeout. Status changes such as
Caps Lock stay in the pill as "Caps Lock · On" without a card.
Transient notifications separate app, title and body with a32px dismiss action.
Codex and Claude notifications use unchanged logo assets from their installed
publisher packages, with source package and hashes recorded beside the assets.
Sender identity selects the mark; mentioning a brand in message text does not.
Theme changes preserve provider colors. Unknown senders use the generic bell.
This banner is not a notification history or an AI permission approval bridge.
Keep Settings vertically scrollable at constrained sizes without horizontal
clipping. Preserve keyboard navigation, task editing and active dialogs.

## Motion

The shell stays anchored at top center; text and artwork never scale. Animate
from current geometry, coalesce unchanged targets, and cancel stale callbacks.

Shell motion is **Ignite** (`ignite_motion.py`), chosen from the interactive
notification studies. Geometry follows damped springs with unit mass, so the
island overshoots once and settles; the height lags the width so the shape
stretches sideways before it drops. Overshoot never leaves the window.

| Event | Timing and treatment |
|---|---|
| Open from the pill | 90ms squash (14 by 4px) while the pill's content fades, then spring: width k420 c25, height k300 c19 with a 35ms lag; about 9% overshoot, settled by 710ms. Content arrives from 190ms over 460ms ease-out: opacity 0 to 1, soft to sharp, rise 10px to 0 |
| Rim light | 1150ms, one clockwise turn of the edge in the theme accent, with a soft aura and a top bloom; fades in over 12%, out over the last 30%. Marks arrivals only (a notification opening from the pill); opening the island yourself stays quiet; never loops |
| Card drop | From 120ms: spring k300 c21 over 560ms from 22px under the island, fading in over the first 60%; lifts away in 200ms ease-in |
| Resize between open shapes | Same spring without squash or rim; content blurs in from 60ms when the state changes |
| Close | 80ms content fade, then spring k520 c30/26 with a slight dip below the pill, settled by 420ms |
| Edge line | 220ms OutCubic geometry; indicator remains opaque black |
| Change feature | 60ms fade out, switch, 100ms fade in |
| Hover | 100ms subtle feedback, no layout movement |

Motion is drawn, not re-laid out: while the shell or card moves, one snapshot of
the content (`content_layer.py`) or banner (`notification_card.py`) is painted
inside the anti-aliased outline, and live widgets return at rest with no graphics
effect. Snapshots soften by a cheap downscale and upscale. If keyboard focus is
inside the island, the content changes in place instead so focus and edits are
untouched. Each frame does one size update and repaints only the island or card.
The overlay window hugs the island at rest (`overlay_fit.py`), grows once before
a transition and shrinks after it, because Windows re-uploads the whole
translucent window for every repaint.

Background decoration is off by default and remains an explicit option. Selected
idle icons and custom GIFs remain independent choices. Springs may overshoot
once per transition; there are no repeated pulses, loops or restarts on pointer
movement, and an interrupted transition clears its blur, rise and rim light.

Reduced motion applies state changes immediately, with no spring, rim light or
blur, and stops background, shine, charging, idle-icon and GIF animation in the
app and live preview. Render a static
representation while retaining saved selections. Auto follows the Windows
animation preference; an unavailable system reading falls back to full motion.

## Preferences and compatibility

- surface_treatment: neutral or tinted; default neutral.
- motion_mode: auto, full or reduced; default auto.
- decorative_effects_enabled: boolean; default false.
- idle_icon: default Aurora. design_version 2 moves a pre-redesign Clock or
  Custom GIF choice to Aurora once; deliberate animated choices stay, and the
  custom GIF path is kept so it can be chosen again.
- compatibility_mode: lets the overlay use the whole screen when needed; it no
  longer pins a full-screen window, which the overlay sizing replaces.

Use detached Settings drafts and explicit Apply/OK/Cancel. Preserve existing
theme, background-animation choice, idle icon, Mumbai location, user tasks, local
file references, media preference and Windows startup choice. Visual refresh must
not persist, create monitors or alter app rules. Existing media APIs remain
compatible even though their source picker is removed from the visible dashboard.

Preserve browser click-to-open and native click-through outside Daisy; hide while
configured games own the foreground. Ten seconds without interaction with Daisy
still produces a black top-edge line, for every pill/notch style. Notifications
must not interrupt protected dialogs or editors. Timer completion, shelf references,
tray recovery and bounded local diagnostics remain working.

## Verification and release

Use focused behavior tests plus the repository's actual verification gate. Review
rapid reversals, notifications during transitions, theme changes, source failures,
font fallback, stable timing widths, reduced motion and Settings cancellation.
Capture real native screenshots for all features, pill/notch, neutral/tinted themes,
constrained windows and100/125/150/200 percent scaling. Inspect contrast, clipping,
alignment, native host masking and click-through; controlled fixtures do not prove
live game, browser or Spotify interaction.

Before replacing the installed X: executable, build and smoke-test it, back up
the executable and preferences, and preserve the configuration's byte hash.
Verify the installed binary, launch, single-instance behavior, Start menu and
startup target. Record checks not run as unverified. No external upload or publish
is implied by saving this document in the repository.

## Requested next phase

After this visual release, investigate battery percentage, an opt-in Windows
notification inbox for apps such as Discord, WhatsApp and Loom, and pending
permission requests from Codex, Claude, Hermes and OpenCode. Permission actions
must use each tool's supported request/response interface, bind to the exact
request and session, and reject expired requests. Where an integration does not
support approval, offer an action to open its owning app. Never infer approval
from a notification, auto-approve, or simulate a successful response.
Validate available integration APIs before settling the implementation design.
