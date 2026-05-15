# Tasks — Band Studio

Status legend: `DONE` (shipped in v1.0.0), `OPEN` (not yet implemented), `[P]` (parallelisable).

## US-1 — Sessions
- [DONE] Create / list / open / delete sessions (`/sessions`).
- [DONE] Session list view + new-session form.
- [DONE] WAL-mode SQLite at `{config_dir}/studio.db`.
- [DONE] Additive schema migrations.

## US-2 — Highway recording
- [DONE] Highway recording overlay with input meter.
- [DONE] Upload pipeline (webm → WAV via ffmpeg).
- [DONE] Pre-play silence trim.
- [DONE] Drift correction > 0.05% via `atempo`.
- [DONE] Input gain 0–300% applied via ffmpeg `volume`.

## US-3 — Mixer recording
- [DONE] Web Audio playback while MediaRecorder captures mic.
- [DONE] Same upload pipeline as US-2.

## US-4 — Punch-in
- [DONE] In/Out point UI.
- [DONE] `POST /tracks/{id}/splice` server-side stitching.
- [OPEN] [P] Crossfade at the splice boundaries (today: hard cuts).

## US-5 — Custom-named tracks
- [DONE] Add track with name + color.
- [DONE] Inline rename, color picker (24 colors).
- [DONE] Reorder via drag (`/sessions/{id}/reorder`).

## US-6 — Audio import
- [DONE] WAV / MP3 / OGG drag-and-drop on a track.
- [DONE] Server conversion to WAV.
- [OPEN] FLAC / AAC import.

## US-7 — Per-track mixing
- [DONE] Volume, pan, mute, solo, offset, fade in / out.
- [DONE] EQ (3-band), compressor, reverb send.
- [DONE] Gear-rack popup UI with SVG rotary knobs.
- [DONE] Live application via `_applyMixToLiveAudio`.
- [DONE] Server persistence via debounced `POST /mix-settings`.

## US-8 — Master bus
- [DONE] Master volume, master limiter toggle.
- [DONE] Real-time peak meter (`AnalyserNode`).

## US-9 — Timeline
- [DONE] Per-track waveform canvases.
- [DONE] Zoom / scroll / Ctrl+wheel.
- [DONE] Markers (manual + import from CDLC sections).

## US-10 — Export
- [DONE] `POST /sessions/{id}/mix?format=mp3|wav`.
- [DONE] ffmpeg combines mix settings.
- [DONE] Download URL returned to client.
- [OPEN] [P] Stem export (per-track WAV bundle as ZIP).
- [OPEN] [P] Loudness target (LUFS) on export.

## US-11 — Demucs
- [DONE] Settings panel (URL + API key).
- [DONE] Test connectivity button.
- [DONE] Extract drums / extract all stems.
- [DONE] Cache results under `{session}/stems/`.
- [OPEN] Progress streaming for long extractions (currently long polling).

## US-12 — Undo / Redo
- [DONE] `Ctrl+Z` / `Ctrl+Y` keybindings.
- [DONE] Toolbar buttons with disabled state.
- [DONE] Debounced for sliders, immediate for toggles.
- [DONE] `MAX_UNDO = 50`.

## US-13 — Practice
- [DONE] **Practice** button opens the song in the highway player.

## Cross-cutting
- [DONE] Idempotent client install (`__slopsmithStudioHooksInstalled`).
- [DONE] Web Audio graph rebuilt on each `_play()`.
- [DONE] Inline migrations for `studio_sessions`, `studio_tracks`, `studio_mix_settings`.
- [OPEN] [P] Golden-render test for client/server mix equivalence (§I).
- [OPEN] [P] ffmpeg presence check at startup with a clear error (Q10).
- [OPEN] [P] Optimistic concurrency for `mix-settings` (Q11).
- [OPEN] [P] Soft-delete (recoverable trash) for sessions.
- [OPEN] Tests — none today.
