# Implementation Plan — Metronome

Single-file front-end-only plugin. No backend, no build step.

## Files

- `plugin.json` — id `metronome`, declares `script: screen.js` only.
  No `nav`, no `routes`, no `settings`, no `screen` HTML.
- `screen.js` (289 lines) — entire implementation.
- `README.md` — user-facing docs.

## Architecture

### Globals (window-scoped, idempotent across re-evals)

| Key | Purpose |
|---|---|
| `MET_SETTINGS_KEY` (`slopsmithMetronomeSettings`) | `{enabled, volume, flashEnabled}` |
| `MET_STATE_KEY` (`slopsmithMetronomeState`) | `{lastBeatIdx, flashAlpha}` |
| `DRAW_HOOK_HIGHWAY_REF_KEY` | Reference to the `highway` instance the draw hook is bound to (lets us rebind cleanly when the renderer is replaced) |
| `TICK_INTERVAL_ID_KEY` | Active `setInterval` handle so reloads can `clearInterval` first |
| `__slopsmithMetronomeHooksInstalled` | Sentinel so the `playSong` wrapper installs once |
| `__slopsmithMetronomeInstalledPlaySongWrapperRef` | Reference to the wrapper currently in `window.playSong` |
| `slopsmithMetronomePlaySongWrapped` | Tag on the wrapper function itself |
| `slopsmithMetronomePlaySongOriginalRef` | Pointer back to the original so re-wraps don't stack |

### Flow

```
setInterval(60Hz)
  ├── _metEnsureDrawHookInstalled()   (binds once per highway instance)
  └── _metTick()
        ├── highway.getBeats() / getTime()  (early-return if absent)
        ├── binary search for current beat idx
        ├── tolerance gate (±50ms)
        ├── update _metState.lastBeatIdx
        ├── _metClick(isMeasure)            (WebAudio sine envelope)
        └── _metFlash(isMeasure)            (sets flashAlpha for draw hook)

addDrawHook((ctx, W, H) =>
  if flashAlpha > 0.005:
    fill amber gradient over y[0.72H..0.90H]
    flashAlpha *= 0.88
)

playSong wrapper:
  reset lastBeatIdx, await original, _metInjectButton()
```

### UI surface

Injected DOM in `#player-controls` (in this order, before the lyrics
button's next sibling):

1. `<button id="btn-metronome">` — toggle, visible always.
2. `<input type="range" id="met-volume">` — visible only when enabled.
3. `<span id="met-vol-label">` — percentage label.
4. `<label id="met-flash-label">` containing `<input id="met-flash-check">`.

`_metSyncUi` flips `.hidden` on the dependent controls based on
`_metSettings.enabled`.

## Integration with Slopsmith Core

- **Read-only**: `highway.getBeats()`, `highway.getTime()`,
  `highway.addDrawHook(fn)`.
- **Write**: appends children to `#player-controls`, wraps
  `window.playSong`. Both operations are idempotent.
- **Audio**: lazily creates a single `AudioContext` on first click.
  The context is shared with whatever else might be on the page.

## Out of Scope

- Build step (none).
- Tests (none — the plugin is a single ~290-line file with no unit-test
  harness in repo).
- Backend routes (none — `routes` is not declared in `plugin.json`).
- CI pipeline (none in repo).
