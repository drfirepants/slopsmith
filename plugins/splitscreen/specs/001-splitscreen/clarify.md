# Clarifications — Split Screen

## Q1: Why is `onSongInfo: () => {}` mandatory on every panel WS?
**A**: Without it, the highway's default `song_info` handler
overwrites the main player's audio src, arrangement dropdown, and
HUD. Each panel WebSocket sees the same `song_info` message; if any
of the N panels uses the default handler, the main player flickers
back to that panel's view. See slopsmith#27 (referenced in
CLAUDE.md:255-256).

## Q2: How is the `_onReady` race resolved?
**A**: `playSong` is wrapped to grab `arrangements` and (optionally)
auto-restart split via `highway._onReady`. Async plugins that
`await` in their wrappers can let `ready` fire before our hook
runs. We poll every 200ms for up to 6 seconds; both paths set
`handled = true` to ensure split is started at most once
(CLAUDE.md "playSong wrapper").

## Q3: Why does `hw.resize` need to be overridden BEFORE `hw.init()`?
**A**: The default `resize()` sizes the highway to the full window
and clobbers siblings. The override sizes to
`panelDiv.getBoundingClientRect()` minus bar height. The override is
applied in `startSplitScreen()` before `initPanel()` to ensure the
first init does not fight the override
(CLAUDE.md "Common pitfalls").

## Q4: Why is `flex-wrap:nowrap;overflow:hidden` on the bar important?
**A**: Buttons are laid out left-to-right in a flex container. Using
`margin-left:auto` would push subsequent buttons in unpredictable
ways when the bar is toggled (some buttons disappear). The
`barToggleBtn` is absolutely positioned outside the flex flow to
sidestep this entirely (CLAUDE.md "Common pitfalls").

## Q5: What does a popup actually load?
**A**: The same Slopsmith app at the same origin, with
`?ssFollower=1` plus serialized panel config. The full bootstrap
runs (app.js + every plugin), then this plugin's IIFE detects
`FOLLOWER` (parsed once at script load, `screen.js:55-74`) and
takes the FOLLOWER path: builds a single full-window panel, opens
`BroadcastChannel('slopsmith-ss')` for time, mutes audio.

## Q6: Why is the popup muted instead of just paused?
**A**: Audio plays from the main window. If the popup also played,
there would be two sources — drift, double-volume, latency mismatch.
Muted lets the highway / lyrics / tab follow the song without
contributing audio.

## Q7: How does layout change preserve arrangement selections?
**A**: `rebuildLayout()` calls `captureCurrentPrefs()` to snapshot
each running panel's state, then tears down and rebuilds. Arrangement
selections are carried across when the new layout has at least as
many panels as the old one; new slots beyond that follow smart
defaults.

## Q8: What is the panel ↔ canvas mapping for external plugins?
**A**: `window.slopsmithSplitscreen.panelIndexFor(canvas)` returns
the panel index for a given canvas element. The 3D highway plugin
uses this to scope per-panel localStorage settings (palette /
background) by index.

## Q9: Plugin load order — why does it matter?
**A**: Screen.js files load alphabetically. Plugins that wrap
`playSong` before splitscreen run closer to the original; later
loaders run first. This affects when `_onReady` is hooked and
whether the poll fallback is needed
(CLAUDE.md "Common pitfalls"). [NEEDS CLARIFICATION: would explicit
load-order metadata in `plugin.json` help here?]

## Q10: What happens to popups when the main window closes?
**A**: They freeze. There is no time source on the BroadcastChannel.
Users must close popups manually (README:62).
[NEEDS CLARIFICATION: should the popup detect main-closed and
self-dismiss?]

## Q11: How is `currentFilename` decoded for pane plugins?
**A**: It may be percent-encoded. Pane plugins MUST call
`decodeURIComponent(filename)` before building the WebSocket URL.
`getWsUrl()` handles this internally for highway connections
(CLAUDE.md "Common pitfalls").
