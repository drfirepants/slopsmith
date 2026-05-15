# Implementation Plan — Split Screen

## Architecture

```
slopsmith-plugin-splitscreen/
├── plugin.json     — id, version 1.4.0, settings, script
├── screen.js       — single IIFE, 2544 lines (see CLAUDE.md for module map)
├── settings.html   — default layout + "Always" + "Remember" checkboxes
├── README.md       — user docs + integration paths
└── CLAUDE.md       — agent guide (the canonical architecture reference)
```

No backend. The plugin is frontend-only; data comes from core's
highway WebSocket and the shared `<audio>` element.

## `screen.js` module map

CLAUDE.md `Module structure` is the canonical map; reproduced briefly:

```
Constants (LAYOUTS, OFF/ON_CLASS, sentinel values, channel cycle)
Module-level state (active, controlsHidden, layout, panels, wrap, ...)
Settings sync (reads settings.html on load)
Panel prefs persistence (savePanelPrefs / loadPanelPrefs / resolveArrIndex)
Helpers (getWsUrl, getDefaultArrangements)
createLyricsPane()
Layout builders (createWrap, applyLayoutStyle, createPanel, sizeCanvases)
Panel lifecycle (populateSelect, initPanel, enter*/exit* mode functions)
Panel interactions (togglePanelTab, toggleDetect, cycleDetectChannel,
                   switchPanelArrangement)
Teardown / rebuild (teardownPanels, rebuildLayout, captureCurrentPrefs)
Start / stop (startSplitScreen, stopSplitScreen, toggle)
Time sync (startTimeSync, stopTimeSync)
Toolbar buttons (createLayoutBtn, createHideBtn, createFloatingShowBtn,
                 togglePanelBar, toggleControlsVisibility, updateBtn,
                 injectBtn)
Hooks into core (wraps window.playSong, window.showScreen)
```

Pop-out adds:
- `popups` Map (main window) — popup metadata.
- `FOLLOWER` constant (popup window) — parsed URL config.
- `ssChannel` — lazily-opened `BroadcastChannel('slopsmith-ss')`.

## Key data structures

### `LAYOUTS`
```js
{ 'top-bottom': {panels:2, style:'flex-col'},
  'left-right': {panels:2, style:'flex-row'},
  'quad':       {panels:4, style:'grid-2x2'} }
```

### Panel pref object (in localStorage `splitscreenPanelPrefs`)
```js
{ arrName, lyrics, inverted, detectChannel, barHidden }
```
`arrName` may be a sentinel: `__lyrics__`,
`__jumping_tab__:<arrName>`, `__3d_highway__:<arrName>`.

### Panel object (in-memory, see CLAUDE.md "Panel object shape")
A composite of DOM refs (`panelDiv`, `canvas`, `bar`, ...buttons)
plus runtime state (`hw`, `arrIndex`, mode booleans, `detector`,
etc.).

## Sequences

### `startSplitScreen()`
1. `createWrap()` — `#splitscreen-wrap` inserted before
   `#player-controls`.
2. `applyLayoutStyle()` — flex direction / grid.
3. For each panel:
   - `createPanel()` — DOM (panelDiv, canvas, bar, buttons).
   - `createHighway()` — fresh highway from core factory.
   - Override `hw.resize()` to size to panel rect minus bar height.
   - `initPanel()` — wire button handlers, connect WebSocket with
     `{ onSongInfo: () => {} }`, set initial mode flags.
   - Wire `barToggleBtn`; restore `prefs.barHidden`.
4. `sizeCanvases()`.
5. `startTimeSync()`.

### `stopSplitScreen()`
1. `savePanelPrefs()`.
2. `teardownPanels()` — destroy resources, remove wrap.
3. Restore `#highway` display, clear control z-index/marginTop.
4. If `controlsHidden`, restore.
5. `stopTimeSync()`.

### `playSong` wrapper
1. Stop active splitscreen.
2. Set `currentFilename` after the original begins loading.
3. Hook `highway._onReady` to grab `arrangements` and re-enter
   splitscreen if `autoReactivate` (race-safe via 200ms poll fallback
   up to 6s).
4. Always call `injectBtn()` so the Split button is present after
   the first song.

## Integration paths (README "Integrating Your Plugin")

### Path 1: Visualization plugins (auto-discovered)
- Declare `"type": "visualization"` and export
  `window.slopsmithViz_<id>()` returning `{init, draw, resize?, destroy?}`.
- Split screen auto-populates each panel's dropdown and calls
  `panel.hw.setRenderer(factory())`. No splitscreen edits required.

### Path 2: Pane plugins (own canvas + own WebSocket)
- Define `window.create<MyViz>({ container }) -> {connect(filename,
  arrIndex), destroy(), resize()}`.
- Splitscreen integration requires adding a sentinel value, a check
  in `populateSelect()`, `enterMyMode` / `exitMyMode`, wire-up in
  `initPanel`, prefs save/restore, sizeCanvases path, teardown.

## DOM / z-index stack (see CLAUDE.md "DOM structure")
```
#player (z:100)
  #highway (default canvas; hidden when split active)
  #splitscreen-wrap (z:3, position:absolute, top:0..bottom:{controlsH})
    .splitscreen-panel
      <canvas>
      .bar (z:5)
      .barToggleBtn (z:6)
      [lyricsPane / jtContainer / tabContainer]
  #player-controls (z:10)
  [floatBtn (z:20) when controls hidden]
```

## Risks

| Risk | Mitigation |
|------|-----------|
| `_onReady` race | 200ms poll up to 6s, single `handled` flag |
| `song_info` clobber | Mandatory `onSongInfo: () => {}` on every WS |
| Resize drift | Funnel through `sizeCanvases()` |
| Re-evaluation of script | Idempotency guards on every wrap / listener |
| Plugin load order | Documented; explicit metadata is open question |
| Popup blocked | User-gesture trigger; documented fallback |
| Main-window closes with popups open | Documented freeze behavior |

## Open items

- Explicit plugin load-order metadata (clarify Q9).
- "Dock all" affordance in main window for popups.
- Popup self-dismissal when main closes (clarify Q10).
- Per-panel persistence of detector enabled state (currently NOT
  re-enabled on load to require microphone gesture).
