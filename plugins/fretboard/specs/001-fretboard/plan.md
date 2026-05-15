# Implementation Plan — Fretboard View

## Architecture

**Frontend-only plugin** (no `routes.py`). Single file: `screen.js` (332 lines). No `screen.html` — DOM is built imperatively.

**Lifecycle**:
1. Load: `screen.js` evaluated once (guarded by `__slopsmithFretboardHooksInstalled`).
2. Wrap `window.playSong` so the toggle button is re-injected after every song load.
3. On toggle ON: create absolute-positioned canvas inside `#player`, insert before `#player-controls`. Add a sibling `✕` dismiss button.
4. `_fbDraw` runs as a `requestAnimationFrame` loop while the canvas exists.
5. On toggle OFF: remove canvas + dismiss button + resize listener.

**State** (module-scope):
- `_fbEnabled` — toggle state.
- `_fbCanvas`, `_fbCtx`, `_fbDismissBtn` — DOM refs.

**Drawing**:
- 6 strings × 24 frets, dot markers at standard positions.
- Active-note query via `_fbGetActiveNotes(t, notes, chords)`:
  - Includes notes with `t - window ≤ noteEnd` AND `n.t ≤ t + window` (window = 0.08s).
  - Sustain alpha = 1 → 0.3 over the sustain length.
  - Notes sorted by time → early break on `n.t > t + 0.5`.
- Display string ordering is reversed (display row 0 = high-e, row 5 = low-E) so the visual matches looking down at a real fretboard.

## Integration Points (Slopsmith core)

| Surface | How used |
|---|---|
| `window.playSong` | hooked once to inject the toggle button per song open |
| `highway.getTime()` | per-frame current time |
| `highway.getNotes()` | per-frame note list (sorted by time) |
| `highway.getChords()` | per-frame chord list |
| `#player` DOM container | canvas mount point |
| `#player-controls` DOM container | toggle button mount point + canvas position anchor |

## File Map

| Path | Purpose | Lines |
|---|---|---|
| `plugin.json` | manifest (id, script) | ~10 |
| `screen.js` | toggle, canvas lifecycle, draw loop | 332 |
| `README.md` | install + how it works | ~40 |

## Tech Stack

- Vanilla JS, canvas 2D.
- No external libraries.
- Tailwind classes for the toggle button styling (inherited from core stylesheet).

## Out-of-Plan / Won't Build

- Bass / extended-range string counts.
- Microphone / scoring.
- Editing.
- Splitscreen-aware factory (it's a legacy overlay).
- Persistent toggle across reloads (currently session-only via module state).
