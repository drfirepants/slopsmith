# Tasks — Split Screen

## US-1: Activate split with smart defaults

- [x] **DONE** `LAYOUTS` definitions (`screen.js:11-15`).
- [x] **DONE** `startSplitScreen` orchestration.
- [x] **DONE** `getDefaultArrangements` lead→rhythm→bass wrap fill.
- [x] **DONE** `injectBtn` adds Split button to player toolbar.
- [x] **DONE** `_onReady` race resolution via 200ms poll (6s budget).

## US-2: Layout switching

- [x] **DONE** `createLayoutBtn` + select handler.
- [x] **DONE** `rebuildLayout` with `captureCurrentPrefs` carry-over.
- [x] **DONE** Persistent `splitscreenLayout` key.
- [ ] **OPEN [P]** Animated transition between layouts.

## US-3: Per-panel renderer

- [x] **DONE** Sentinel values for lyrics, jumping tab, 3D highway.
- [x] **DONE** `populateSelect` capability-checks each external
  factory.
- [x] **DONE** `enter*Mode` / `exit*Mode` for each mode.
- [x] **DONE** Mode exclusivity (constitution §VIII).
- [ ] **OPEN [P]** Document the sentinel-value protocol in README
  more prominently for plugin authors.

## US-4: Per-panel toggles

- [x] **DONE** Invert.
- [x] **DONE** Lyrics toggle.
- [x] **DONE** Tab overlay (`createTabView` from external plugin).
- [x] **DONE** Detect (with `M|L|R` channel cycle).
- [x] **DONE** State persisted per panel.

## US-5: Hide controls / mini bars

- [x] **DONE** `toggleControlsVisibility` + floating restore pill.
- [x] **DONE** `togglePanelBar` per panel.
- [x] **DONE** Both states persisted.
- [x] **DONE** `sizeCanvases` recalculates after toggles.

## US-6: Pop-out

- [x] **DONE** `?ssFollower=1` URL flag detection (`FOLLOWER`).
- [x] **DONE** Popup builds single full-window panel.
- [x] **DONE** `BroadcastChannel('slopsmith-ss')` time sync.
- [x] **DONE** Popup muted.
- [x] **DONE** Dock returns panel to original slot.
- [x] **DONE** Popup auto-follows when main loads a different song.
- [ ] **OPEN [P]** Detect main-closed and self-dismiss (clarify Q10).
- [ ] **OPEN [P]** "Dock all" affordance in main window.

## US-7: Layouts inside the popup

- [x] **DONE** Popup's own bottom toolbar with layout picker.
- [x] **DONE** Popup's layouts independent of main and other popups.
- [x] **DONE** Smart-defaults fill new slots.

## Settings

- [x] **DONE** Default layout select.
- [x] **DONE** Always-split checkbox.
- [x] **DONE** Auto-reactivate checkbox.

## External integration

- [x] **DONE** Capability checks for `createJumpingTabPane`,
  `slopsmithViz_highway_3d`, `createTabView`, `createNoteDetector`.
- [x] **DONE** README "Path 1" auto-discovery for visualization
  plugins via `slopsmithViz_<id>()`.
- [x] **DONE** README "Path 2" pane-plugin contract documented.
- [ ] **OPEN [P]** Add a runtime self-test page that exercises both
  paths.

## Robustness

- [x] **DONE** Idempotent `playSong` / `showScreen` wrappers.
- [x] **DONE** `sizeCanvases` is the single resize entry.
- [x] **DONE** `onSongInfo: () => {}` on every panel WS.
- [ ] **OPEN [P]** Explicit plugin load-order metadata (clarify Q9).

## Spec-kit hygiene

- [x] **DONE** Constitution.
- [x] **DONE** Spec / clarify / plan / tasks / analyze.
- [x] **DONE** CLAUDE.md is already a high-quality agent guide and
  is preserved as the canonical architecture reference.
