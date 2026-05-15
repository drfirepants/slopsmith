# Implementation Plan — Drum Highway

## Architecture

**Frontend-only plugin** (no `routes.py`). All logic lives in `screen.js` (1782 lines).

**Renderer registration**: `window.slopsmithViz_drums = createFactory` exposes a factory that Slopsmith core invokes via `setRenderer` (slopsmith#36). Each call returns a per-instance object owning its own canvas, scoring state, and MIDI handlers.

**Per-instance state (Wave C)** closured in `createFactory()`:
- `_drumCanvas`, `_drumCtx`, `_overlayDiv`
- Held-pad state, lane-flash timers, streak counter, accuracy %
- Settings-panel DOM nodes anchored to the panel's gear icon
- Resize listener (added on init, removed on teardown)

**Module-scope state** (intentional):
- `_cfg` (settings cache, hydrated from localStorage)
- `_audioCtx` + WebAudioFont preset (one AudioContext per browser)
- `_cfg.learnLane` (global learn intent)

**MIDI routing**:
- One `navigator.requestMIDIAccess()` subscription, attached at first init.
- Per note-on, the global handler asks `slopsmithSplitscreen.isActive(id)` for each registered instance and dispatches to the focused one.
- Focus change clears outgoing-panel held-pad / lane-flash state.

## Integration Points (Slopsmith core)

| Surface | How used |
|---|---|
| `window.slopsmithViz_drums = createFactory` | renderer registration |
| `createFactory.matchesArrangement(songInfo)` | Auto-mode selection |
| Renderer `init({canvas, container, bundle})` | per-instance start |
| Renderer `draw(ctx, bundle, t, dt)` | each animation frame |
| Renderer `dispose()` | teardown |
| `bundle.notes`, `bundle.chords`, `bundle.isReady` | data input |
| `bundle.stringCount` (slopsmith#93) | not directly used (drums lanes are fixed at 8); referenced for parity |
| `window.slopsmithSplitscreen.isActive(id)` | focus oracle |

## File Map

| Path | Purpose | Lines |
|---|---|---|
| `plugin.json` | manifest (id, type, script) | ~9 |
| `screen.js` | factory, draw loop, MIDI, scoring, settings UI, validators | 1782 |
| `README.md` | features, lane table, custom-mapping how-to | ~100 |
| `screenshot.png` | hero image | — |

## Tech Stack

- Vanilla JS, Tailwind classes (inherited from Slopsmith core stylesheet).
- Canvas 2D, DPR-scaled.
- Web MIDI API.
- WebAudioFont (CDN-hosted GM drum preset, loaded once).

## Notable Design Decisions

- **Word-boundary matcher** (`\b...\b`) instead of substring — locks out false positives like "Drumstick".
- **Edge-detected `bundle.isReady`** in draw() instead of subscribing to a global `song:ready` bus event — correct for N panels without cross-instance fan-out.
- **Validator-first localStorage** — every persisted read is sanitised, so synced profiles or manual edits can't crash the plugin.

## Out-of-Plan / Won't Build

- E-drum acoustic trigger detection.
- Microphone-based drum hit detection.
- Latency calibration UI (currently relies on the user's audio path being stable).
- Recording / authoring drums (delegate to editor plugin).
