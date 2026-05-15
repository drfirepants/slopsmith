# Feature Specification: Split Screen

**Plugin id**: `splitscreen` (`plugin.json:2`)
**Settings**: `settings.html` (`plugin.json:6`)
**Status**: Shipped (v1.4.0)

## Summary

Renders 2–4 independent highway panels side-by-side in the player.
Each panel is its own highway instance with its own WebSocket and
arrangement, all slaved to the main `<audio>` element. Supports
three layouts (Top/Bottom, Left/Right, Quad), per-panel
visualization plugins (3D highway, lyrics, jumping tab), per-panel
note detection on a chosen audio channel, and pop-out into a second
browser window for multi-monitor practice.

## User Stories

### US-1 — Split with smart defaults
**As** a user opening a song with multiple arrangements
**I want** to click Split and see lead / rhythm / bass auto-assigned
**So that** I can practice multiple arrangements simultaneously.

- **Given** the user is in the player
- **When** they click the Split button (`screen.js: injectBtn`)
- **Then** `startSplitScreen()` builds the wrap, panels, highway
  instances, and connects each to
  `/ws/highway/{filename}?arrangement={index}`.
- **And** the default panel arrangements follow lead → rhythm → bass,
  wrapping if there are fewer arrangements than panel slots
  (`getDefaultArrangements`).

### US-2 — Switch layouts
**As** the same user
**I want** Top/Bottom, Left/Right, or Quad
**So that** I can fit my screen.

- **Given** Split is active
- **When** the user picks a layout from the player toolbar select
  (`createLayoutBtn`)
- **Then** `rebuildLayout()` captures `captureCurrentPrefs()`, tears
  down panels, rebuilds with the new count, and carries arrangement
  selections across when the new layout has at least as many panels
  as the old one.
- **And** the choice is persisted to `localStorage:splitscreenLayout`.

### US-3 — Per-panel renderer (highway / lyrics / jumping tab / 3D)
**As** a user with the related plugins installed
**I want** each panel's dropdown to offer Lyrics, Jumping Tab, and 3D
Highway alongside arrangements
**So that** I can mix renderers across panels.

- **Given** the relevant external factory exists on `window`
- **When** the user picks an option whose value is a sentinel
  (`__lyrics__`, `__jumping_tab__:N`, `__3d_highway__:N`)
- **Then** the corresponding `enter*Mode(panel)` runs and the others
  exit, per the mode-exclusion rule (constitution §VIII).

### US-4 — Per-panel invert / lyrics / tab / detect
**As** the same user
**I want** to flip a single panel between player and audience
perspective, toggle lyrics overlay, toggle tab overlay, enable note
detect on a chosen audio channel
**So that** each panel matches a different practice need.

- **Given** Split is active
- **When** the user clicks `Invert` / `Lyrics` / `Tab` / `Detect` /
  `M|L|R` channel button on a panel's mini bar
- **Then** the plugin updates the panel's state, persists prefs, and
  (for Detect) instantiates `createNoteDetector(...)` on the chosen
  channel.

### US-5 — Hide controls and per-panel mini bars
**As** a user wanting maximum highway space
**I want** to hide the global controls bar and individual panel
mini bars
**So that** the highway fills the screen.

- **Given** Split is active
- **When** the user clicks `▾ Bar` next to Close
- **Then** `toggleControlsVisibility()` hides `#player-controls`,
  `sizeCanvases()` recalculates with the freed pixels, and a
  floating `▴ Controls` pill appears.
- **When** the user clicks a panel's `▾ Bar`
- **Then** `togglePanelBar(panel)` hides that panel's mini bar; its
  highway resizes to fill the panel.

### US-6 — Pop a panel into its own window
**As** a multi-monitor user
**I want** to click `⇱ Pop` and drag the new window to a second monitor
**So that** the highway / lyrics / tab can live on its own screen
without the controls.

- **Given** the user clicks `⇱ Pop` on a panel
- **When** `window.open(?ssFollower=1&...)` succeeds
- **Then** the popup boots Slopsmith with the panel config in URL
  params, runs the same screen.js IIFE, but takes the FOLLOWER path
  and renders a single full-window panel slaved to the main window's
  audio via `BroadcastChannel('slopsmith-ss')`.
- **And** the popped panel disappears from the main layout (slot
  collapses; if only one panel remained, main reverts to default
  highway).
- **And** the popup is muted.
- **When** the user clicks `⇲ Dock` or closes the window
- **Then** the panel returns to its original slot with its current
  state preserved.

### US-7 — Split the popped window further
**As** the same user
**I want** the popup to also support Single / Top-Bottom / Left-Right /
Quad
**So that** I can run e.g. a quad of all four arrangements on the
second monitor while the main window stays single.

- **Given** a popup is open
- **When** the user picks a layout from the popup's bottom toolbar
- **Then** the popup tears down its single panel and rebuilds with
  N panels using lead → rhythm → bass smart defaults, independent
  of the main window.

## Functional Requirements

- **FR-1** Three layouts: top-bottom (2P), left-right (2P), quad
  (4P) — `LAYOUTS` (`screen.js:11-15`).
- **FR-2** Each panel: its own WebSocket to
  `/ws/highway/{filename}?arrangement={index}`; `onSongInfo:
  () => {}` is mandatory.
- **FR-3** Time sync: 60fps `setInterval` reads
  `audio.currentTime` and calls `panel.hw.setTime(t)` per panel
  (`startTimeSync`).
- **FR-4** Renderer integration via `panel.hw.setRenderer(factory())`
  for visualization plugins, or pane-factory `{container} → {connect,
  destroy, resize}` for full-canvas plugins (README "Path 2").
- **FR-5** Persistence: layout, autoReactivate, alwaysSplit,
  controlsHidden, per-panel `splitscreenPanelPrefs` array.
- **FR-6** `sizeCanvases()` is the only resize entry point; it
  recalculates `wrap.style.bottom` from `controls.offsetHeight`
  and per-panel `hw.resize()` / `jumpingTabPane.resize()`.
- **FR-7** Pop-out: `?ssFollower=1` URL flag triggers FOLLOWER mode
  in the same script; FOLLOWER takes a panel config from URL params
  and slaves to `BroadcastChannel('slopsmith-ss')` for time.
- **FR-8** Mode exclusivity per panel; entering one mode must exit
  the others.
- **FR-9** Detect channel cycle: M → L → R; persisted per panel
  (`DETECT_CHANNEL_CYCLE`).
- **FR-10** `_onReady` race resolved with a 200ms poll up to 6s
  (CLAUDE.md "playSong wrapper").
- **FR-11** Settings: layout dropdown, "Always enter split screen"
  checkbox, "Remember split screen between songs" checkbox
  (`settings.html:5-24`).

## Non-Functional Requirements

- **NFR-1** No re-wrap of `playSong` / `showScreen` on script
  re-evaluation.
- **NFR-2** Capability-check before exposing any external-plugin
  feature.
- **NFR-3** Smart defaults preserve existing arrangement selections
  on layout change when panel count is preserved or grows.
- **NFR-4** Popups freeze when the main window closes — explicit and
  documented (README:62).

## Out of Scope

- More than 4 panels.
- Cross-tab synchronization beyond pop-out (no follow-mode for
  unrelated tabs).
- Cancelling a popup remotely from the main window
  [NEEDS CLARIFICATION: should there be a "Dock all" affordance in
  main?].

## Key Entities

- **Panel**: `{ panelDiv, canvas, bar, barToggleBtn, select, arrName,
  invertBtn, ..., hw, arrIndex, lyricsMode, lyricsPane,
  jumpingTabMode, jumpingTabPane, hw3dMode, tabActive, tabInstance,
  detectChannel, detector, ... }` — see CLAUDE.md "Panel object shape".
- **Layout**: `{ panels: N, style: 'flex-col' | 'flex-row' | 'grid-2x2' }`.
- **Pref object**: `{ arrName, lyrics, inverted, detectChannel,
  barHidden }` per panel slot.
- **FOLLOWER**: parsed-once URL config in popup mode.
