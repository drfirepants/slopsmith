# Spec — Band Studio (`studio`)

> Retrospective spec for shipped v1.0.0. The implementation in `routes.py`
> (1424 lines), `screen.js` (2856 lines), and `screen.html` (340 lines) is the
> source of truth.

## Summary

A collaborative band recording and mixing plugin. Users create a session
against a song from their Slopsmith library, record (on the highway or in the
mixer view), import audio, layer takes, mix with per-track effects (EQ,
compressor, reverb send, fades, offsets), and export a final mix as MP3 or
WAV. Optional Demucs integration extracts drums/bass/vocals/other stems via
a remote GPU server.

## User stories

### US-1 — Create a session
- **Given** I open **Studio** from the nav,
  **When** I click **+ New Session**, fill in name and pick a song from the
  library autocomplete (`POST /api/plugins/studio/sessions`),
  **Then** a session row is created (`studio_sessions`) and I'm taken to the
  mixer view.

### US-2 — Record on the highway
- **Given** I open a session,
  **When** I click the highway-record button,
  **Then** the highway plays the song while my microphone records via
  `MediaRecorder`. A small overlay shows input level metering.
- On stop, the webm is uploaded
  (`POST /api/plugins/studio/sessions/{id}/upload`); the server converts to
  WAV via ffmpeg, applies optional input gain (0–300%), trims pre-play
  silence, and corrects clock drift > 0.05% via `atempo`.

### US-3 — Record in mixer view
- **Given** I'm in the mixer,
  **When** I click record on a track,
  **Then** the Web Audio engine plays all currently-active tracks and the
  song while `MediaRecorder` captures my mic. On stop the upload pipeline
  matches US-2.

### US-4 — Punch-in recording
- **Given** I have an existing take with regions I want to redo,
  **When** I set in/out points and click **Punch record**
  (`POST /api/plugins/studio/tracks/{id}/splice`),
  **Then** the new performance is spliced into the existing track at the in
  point, preserving everything before and after.

### US-5 — Add a custom-named track
- **Given** I'm in the mixer,
  **When** I click **+ Track** and name it (e.g. "Lead Double"),
  **Then** the track is created (`POST sessions/{id}/add-track`) and appears
  in the order I drop it via reorder (`POST sessions/{id}/reorder`).

### US-6 — Import an external audio file
- **Given** I have a vocal recorded on my phone,
  **When** I drag-and-drop a WAV/MP3/OGG onto a track
  (`POST tracks/{id}/import-audio`),
  **Then** the file is converted to WAV server-side and becomes the active
  take for that track.

### US-7 — Per-track mixing
- Volume (0–150%), pan (-100..+100), mute, solo, time offset (ms), fade in /
  fade out (ms) all dispatch `POST sessions/{id}/mix-settings` (debounced)
  and apply live to the Web Audio nodes via `_applyMixToLiveAudio`.
- Three effects per track, opened via gear-rack popups:
  - **EQ**: 3-band biquad shelves/peaks (200 Hz low shelf, 1 kHz mid peak,
    4 kHz high shelf) -12..+12 dB.
  - **Compressor**: threshold (-60..0 dB), ratio (1..20), attack (1..100 ms),
    release (10..1000 ms). Bypassed when ratio is 1.
  - **Reverb send**: 0..100% to a shared `ConvolverNode` with a generated
    2 s room IR.

### US-8 — Master bus
- Master volume (0–200%), master limiter on/off (a `DynamicsCompressor` set
  as a hard limiter at 0 dBFS), real-time peak meter via `AnalyserNode`.

### US-9 — Timeline
- Per-track waveform canvases tinted with track colour.
- Zoom (`_zoomLevel`), horizontal scroll (`_scrollOffset`), Ctrl+wheel zoom.
- Markers (named timeline points) added manually
  (`POST sessions/{id}/markers`), renamed/deleted, or imported from the
  song's CDLC sections (`POST sessions/{id}/import-markers`).

### US-10 — Export
- **Given** the user clicks **Export**,
  **When** the request hits `POST sessions/{id}/mix?format=mp3|wav`,
  **Then** the server runs ffmpeg combining all active tracks with their
  mix settings (volume, pan, EQ, compressor, reverb send, fades, offsets,
  master volume + limiter) and returns a download link.

### US-11 — Stem separation (Demucs)
- **Given** the user has configured the Demucs URL + API key
  (`POST /demucs/config`),
  **When** they click **Extract Drums** or **Extract All Stems**
  (`POST sessions/{id}/extract-drums`, etc.),
  **Then** Studio POSTs the song audio to the configured Demucs server
  (model `htdemucs_ft`, `--shifts 2`), caches the result, and creates new
  tracks for each returned stem.
- If Demucs is unconfigured or unreachable, the call returns an error and
  the rest of the studio remains usable.

### US-12 — Undo / Redo
- Ctrl+Z / Ctrl+Y bound at the document level when Studio is mounted.
- Stack of `JSON.stringify(_mixState)` snapshots, debounced for slider
  changes, immediate for toggles, max 50.
- Visual buttons greyed when stacks are empty.

### US-13 — Practice from a session
- **Given** a session is open,
  **When** I click **Practice**,
  **Then** the song opens in the highway player so I can rehearse before
  recording.

## Functional requirements (selected)

| ID    | Requirement                                                                                  | Source                              |
|-------|----------------------------------------------------------------------------------------------|-------------------------------------|
| FR-1  | Persist sessions, tracks, mix settings, markers in SQLite at `{config_dir}/studio.db` (WAL). | `routes.py` `_get_db`               |
| FR-2  | Migrate schema additively (`ALTER TABLE … ADD COLUMN` with DEFAULT).                          | `routes.py` migrations              |
| FR-3  | Convert uploaded webm → WAV via ffmpeg before storing.                                        | `routes.py` upload handler          |
| FR-4  | Apply server-side input gain via ffmpeg `volume`.                                             | `routes.py` upload handler          |
| FR-5  | Detect & correct drift > 0.05% via `atempo`.                                                  | `routes.py` upload handler          |
| FR-6  | Splice (punch-in) preserves audio before/after the in/out window.                             | `routes.py` `/tracks/{id}/splice`   |
| FR-7  | Idempotent client install via `__slopsmithStudioHooksInstalled` flag.                         | `screen.js` top                     |
| FR-8  | Web Audio graph rebuilt on every `_play()`, torn down on `_pause()`.                          | `screen.js` `_play` / `_pause`      |
| FR-9  | Per-track mix changes debounced via `_debounceSaveMix`.                                       | `screen.js`                         |
| FR-10 | Undo stack capped at `MAX_UNDO = 50`, identical consecutive snapshots dropped.                | `screen.js` `_pushUndo`             |
| FR-11 | Master limiter modelled by `DynamicsCompressor` configured as hard limiter.                   | `screen.js`                         |
| FR-12 | Reverb is a `ConvolverNode` with a generated 2 s room impulse response, shared bus.           | `screen.js` `_createReverbBus`      |
| FR-13 | Drag-and-drop import accepts WAV/MP3/OGG.                                                     | `screen.html` + JS                  |
| FR-14 | `POST /demucs/test` validates server connectivity and API key before extraction.              | `routes.py` `/demucs/test`          |
| FR-15 | Export endpoint returns download URL (file under `{config_dir}/studio/{id}/exports/`).        | `routes.py` `/sessions/{id}/mix`    |

## Non-functional

- **Latency**: parameter UI → audible change ≤ 16 ms.
- **Mix equivalence**: client-side Web Audio mix and server-side ffmpeg mix
  must be perceptually equivalent (constitution §I). Verified by ear today.
- **Storage**: per-session directory under `{CONFIG_DIR}/studio/{session_id}/`.
- **Browser**: Chrome/Edge for MediaRecorder webm and broad Web Audio
  feature coverage. Safari/Firefox compatibility is best-effort.

## Out of scope

- Multi-user real-time collaboration (the README says "collaborative" but the
  workflow is asynchronous file sharing, not OT/CRDT live editing).
- MIDI tracks (audio-only).
- Time-stretching independent of pitch (use offsets instead).
- VST hosting (covered by `slopsmith-desktop`).

## Open clarifications

- [NEEDS CLARIFICATION] Authentication on `/demucs/*` — the API key is sent
  in headers; server-side validation behaviour on bad keys is implicit.
- [NEEDS CLARIFICATION] Behaviour when ffmpeg is missing on the host (the
  Slopsmith Docker image ships it, but `slopsmith-desktop` may not).
- [NEEDS CLARIFICATION] Concurrent edits to the same session from two
  browsers — last-write-wins on mix settings; no optimistic concurrency.
- [NEEDS CLARIFICATION] Soft delete vs hard delete — `DELETE
  /sessions/{id}` removes the row and the directory; there is no
  recoverable trash.
