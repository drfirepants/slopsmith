# Implementation Plan — Jumping Tab

## Architecture

**Frontend-only**, ~1714 lines in `screen.js`, plus a standalone demo and test harness.

**Renderer registration**: `window.slopsmithViz_jumpingtab = createFactory` exposes a factory that Slopsmith core invokes via `setRenderer` (slopsmith#36). Factory returns a per-instance object owning canvas, caches, and listeners.

**Module scope**: pure helpers (geometry, time→x mapping, trajectory builder, bezier interpolation, range search) — stateless and exercised directly by `test/test.html`.

**Per-instance (Wave C)** closured in `createFactory()`:
- canvas + ctx
- chart cache (notes / chords mapped to draw structures)
- trajectory cache (bezier curves between consecutive notes)
- technique-arc cache
- listener refs (`_onWinResize`)

**Demo state** (preserved from pre-Wave-C): `window.__jumpingtab_state` and `window.__jumpingtab_demo` keep the module-level mini-state alive so existing `test/test.html` and `demo/index.html` bindings still work.

**Draw chain** (per frame):
1. Resize check (DPR-aware).
2. Re-resolve string count from `bundle.stringCount` (slopsmith#93) on bundle change.
3. Range-search active notes within `[t - BEHIND, t + AHEAD]`.
4. Render lanes, beat ticks, section bands, progress bar.
5. Render trajectories (cached unless bundle.notes / bundle.chords reference-changes).
6. Render notes / chords / techniques.
7. Render hopping ball.
8. Render impacts (`DISABLE_RINGS` short-circuit).
9. Render chord-box secondary canvas.

## Integration Points (Slopsmith core)

| Surface | How used |
|---|---|
| `window.slopsmithViz_jumpingtab = createFactory` | renderer registration (slopsmith#36) |
| Renderer `init / draw / dispose` lifecycle | per-instance |
| `bundle.notes`, `bundle.chords` | input data; reference-change triggers trajectory rebuild |
| `bundle.stringCount` (slopsmith#93) | dynamic lane count |
| `bundle.chords[i].template` (slopsmith#92) | chord-template lookup for chord-box render |
| `bundle.sections`, `bundle.beats` | section bands + beat ticks |
| `bundle.isReady` | edge-detected per-instance |

## File Map

| Path | Purpose | Lines |
|---|---|---|
| `plugin.json` | manifest (id, type, script) | ~9 |
| `screen.js` | factory, draw chain, helpers, demo bindings | 1714 |
| `test/test.html` | zero-dep browser test harness for pure helpers | — |
| `demo/index.html` | standalone scene renderer (overview, techniques, fast) | — |
| `demo/index.html?scene=...` | screenshot scenes for README | — |
| `screenshots/*.png` | hero images | — |
| `README.md` | features, architecture, attributions, demo recipe | ~120 |

## Tech Stack

- Vanilla JS, single IIFE in `screen.js`.
- Canvas 2D, DPR-scaled, two canvases (main tab + chord box overlay).
- Stateless math helpers at module scope.
- Headless Chrome (developer-side) for screenshot regen via `demo/index.html?scene=*`.

## Visual Constants (key ones)

| Constant | Value | Purpose |
|---|---|---|
| `AHEAD` | 5.5 s | lookahead window |
| `BEHIND` | 1.2 s | trailing window |
| `HIT_LINE_FRAC` | 0.18 | hit-line position (fraction of canvas width) |
| `FADE_SECONDS` | 1.0 | post-hit fade duration |
| `SQUASH_WINDOW_MS` | 60 | ball squash on hit |
| `IMPACT_DURATION` | 0.45 s | impact animation length |
| `DISABLE_RINGS` | true | opt out of expanding hit-line rings |
| `TOP_PAD` | 60 px | canvas top padding |
| `BOTTOM_PAD` | 36 px | canvas bottom padding (progress bar etc) |

## Out-of-Plan / Won't Build

- Microphone input / scoring.
- Settings panel (speed / colors / visibility window).
- Standalone full-screen mode.
- Auto-activation (`matchesArrangement`).
