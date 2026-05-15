# Plan — Band Studio (as built)

## File map

| File             | Lines | Purpose                                                                  |
|------------------|-------|--------------------------------------------------------------------------|
| `plugin.json`    | 9     | Manifest. `id: studio`, version `1.0.0`, nav `Studio`, declares `screen.html`/`screen.js`/`routes.py`. |
| `routes.py`      | 1424  | FastAPI backend: SQLite schema + migrations, file management, ffmpeg pipelines, Demucs proxy, mix export, marker import. |
| `screen.html`    | 340   | Session list view, new-session form, mixer view, Demucs settings panel.  |
| `screen.js`      | 2856  | Web Audio playback graph, MediaRecorder, waveform rendering, undo/redo, FX knobs, transport, marker bar. IIFE with `window.studio*` exports. |
| `screenshot.png` | —     | README screenshot (binary).                                              |

## Backend layout (`routes.py`)

### Tables
- `studio_sessions(id, song_filename, name, created_by, created_at, master_volume, master_limiter)`
- `studio_tracks(id, session_id, instrument, recorded_by, take_number, audio_path, duration, created_at, is_active, track_name, sort_order, color)`
- `studio_mix_settings(id, session_id, track_id, volume, pan, muted, solo, offset_ms, fade_in_ms, fade_out_ms, eq_low, eq_mid, eq_high, reverb_send, comp_threshold, comp_ratio, comp_attack, comp_release)` — UNIQUE(session_id, track_id)
- `studio_markers(id, session_id, time, name, color)`

WAL mode, additive migrations on every connect.

### Endpoints (28 total)
- Sessions: `GET /sessions`, `POST /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`
- Recording / upload: `POST /sessions/{id}/upload`
- Tracks: `DELETE /tracks/{id}`, `POST /tracks/{id}/activate`, `POST /tracks/{id}/rename`, `POST /tracks/{id}/color`, `POST /tracks/{id}/import-audio`, `POST /tracks/{id}/splice` (punch-in)
- Track ordering: `POST /sessions/{id}/add-track`, `POST /sessions/{id}/reorder`
- Markers: `POST /sessions/{id}/markers`, `DELETE /markers/{id}`, `POST /markers/{id}/rename`, `POST /sessions/{id}/import-markers`
- Mix: `GET /sessions/{id}/mix-settings`, `POST /sessions/{id}/mix-settings`, `POST /sessions/{id}/master`, `POST /sessions/{id}/mix` (export)
- Audio serving: `GET /tracks/{id}/audio`, `GET /sessions/{id}/song-audio`
- Demucs: `GET /demucs/config`, `POST /demucs/config`, `POST /demucs/test`, `POST /sessions/{id}/extract-drums` (and equivalent for all-stems)
- Misc: `GET /gear-image/{name}`

### Filesystem
```
{CONFIG_DIR}/
  studio.db
  studio/
    {session_id}/
      take_{n}.wav        (recorded / converted)
      stems/              (demucs cache)
      exports/            (mix output)
```

## Frontend layout (`screen.js`)

### Major modules (by function name prefix)
- **Session list / new-session form**: `_renderSessionList`, `studioCreateSession`, `studioOpenSession`, `studioBackToList`.
- **Audio engine**: `_getAudioCtx`, `_createReverbBus`, `_play`, `_pause`, `_stopAllSources`, `_applyMixToLiveAudio`, `_applyAllMixToLive`.
- **Transport / animation**: `_startAnimLoop`, `_stopAnimLoop`, `_drawAllCursors`, `studioTogglePlay`, `studioStop`, `studioSeek`.
- **Recording**: `studioToggleRecord`, `_stopRecording`, highway recording overlay (`_createHwOverlay`, `_updateHwOverlay`, `_startHwMeter`, `_hwDrawHook`, `_stopHighwayRecording`, `_cleanupHwAudio`), punch-in (`_populatePunchTrackSelect`, `studioPunchSetIn/Out/Record`, `_stopPunchRecord`).
- **Mix**: `studioSetVolume/Pan/Offset/Fade/Eq/ReverbSend/Comp`, `studioToggleMute/Solo`, `_hasSoloActive`, `_debounceSaveMix`.
- **Waveforms**: `_drawWaveform`, `_redrawWaveform`, `_initWaveformWheelZoom`, `_clampScroll`.
- **Markers**: `_renderMarkers` and friends.
- **FX UI**: `_createSvgKnob`, `_applyFxKnobValue`, `_describeArc`, `_polarToCartesian` (gear-rack popups with rotary SVG knobs).
- **Master meter**: `_startMasterMeter`, `_debounceSaveMaster`.
- **Undo**: `_pushUndo`, `_captureUndoNow`, `_applyRestoredMixState`, `_updateUndoButtons`, `studioUndo`, `studioRedo`.
- **Settings**: `_loadSettings`, `_saveSettings`.
- **Boot**: `_runStudioInit`, `studioInit` (called when Studio screen activates).

### Web Audio graph (per play)
```
song (decoded AudioBuffer) ─► AudioBufferSourceNode ─► gain ─► pan ┐
                                                                   │
each track:                                                        │
   AudioBuffer ─► Source ─► EQ chain (low/mid/high biquad) ┐       │
                                                           ├─►compressor─►gain─►pan─┐
                                            reverb send ──►│                        │
                                                           │  ┌─►ConvolverNode─►reverbGain─┐
                                                           └──┘                            ▼
                                                                                       masterGain ─► limiter ─► analyser ─► destination
```

## Idempotency and exports

```js
if (window.__slopsmithStudioHooksInstalled || window.__slopsmithStudioHooksInstalling) return;
…
window.studioInit = …
window.studioUndo = …  // ~30 named exports
window.__slopsmithStudioHooksInstalled = true;
```

## Dependencies

- **System**: `ffmpeg`, `ffprobe` (audio conversion / drift correction / export).
- **Browser**: Web Audio API, MediaRecorder, OfflineAudioContext (waveform decode).
- **Optional**: `slopsmith-demucs-server` running externally for stem separation.

## Risks / drift watchpoints

- **Mix equivalence (§I)** — easy to drift between client preview and server
  export. No automated test today. Add a golden-render fixture pass.
- **Schema migrations (§VII)** — additive only; a careless rename would orphan
  rows for older clients.
- **Undo stack semantics (§VI)** — adding a new mix parameter requires updating
  `_applyRestoredMixState` to handle missing keys for older snapshots.
- **Audio paths** — moving `{CONFIG_DIR}/studio/...` between hosts breaks
  `audio_path` rows; they're stored as relative paths from `STUDIO_DIR` to
  ease this.
