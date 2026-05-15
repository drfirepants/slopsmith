# Fretboard View — Plugin Constitution

A complementary horizontal fretboard overlay that lights up active notes as they arrive on the highway. Stays out of the way: a small toggle button in the player controls, an absolute-positioned canvas above the controls bar, and a dismiss `✕`.

## Core Principles

### I. Overlay, Not Replacement
The plugin draws a fretboard on top of the existing highway via an absolute-positioned canvas (`pointer-events: none` on the canvas; `pointer-events: auto` only on the dismiss button). It MUST NOT replace or hide the highway — both views are visible simultaneously. Toggle off → canvas removed, no residual DOM.

### II. Reads, Never Writes, Highway State
The plugin reads `highway.getTime()`, `highway.getNotes()`, `highway.getChords()` once per `requestAnimationFrame`. It never mutates highway state. If the highway API isn't present (e.g. on screens without playback) the plugin's button is still installed but is a no-op when clicked.

### III. Idempotent Hooks
`window.playSong` is wrapped exactly once via `__slopsmithFretboardHooksInstalled`. Toggle state survives song changes (a new song re-injects the button and re-creates the canvas if enabled).

### IV. DPR + Resize Aware
Canvas `bottom` offset is recomputed on every `_fbResize` to track the controls bar (which flex-wraps to multiple rows on narrow viewports). DPR scaling is applied so notes are crisp on high-DPI displays.

### V. Match Rocksmith String Colors
String colors mirror Rocksmith's palette: low-E red, A yellow/gold, D blue, G orange, B green, high-e purple. Active notes use the brighter variant (`FB_STRING_BRIGHT`) plus a multi-layer glow.

## Inherits from Slopsmith Core Constitution

- **Vanilla JS, no framework.**
- **Plugin isolation**: registers via the legacy `window.playSong` wrap pattern (pre-setRenderer plugin model). Frontend-only — no `routes.py`.
- **Manifest-driven loading**: `plugin.json` declares `id: "fretboard"`, no `nav` (button injected at runtime).
- **Single-instance.** No splitscreen-aware factory; plays well as an overlay only on the main player.
- **Read-only consumer of `highway.*` API** (slopsmith core's pre-bundle highway accessors).

**Version**: 1.0.0 | **Ratified**: 2026-05-09 | **Last Amended**: 2026-05-09
