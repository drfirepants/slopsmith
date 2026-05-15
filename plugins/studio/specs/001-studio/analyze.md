# Analyze — Band Studio

## Coverage

| Area              | Spec | Plan | Code           | Notes                                  |
|-------------------|------|------|----------------|----------------------------------------|
| Sessions / DB     | ✅   | ✅   | `routes.py`    | SQLite + WAL + additive migrations     |
| Recording         | ✅   | ✅   | both           | Highway + mixer modes                  |
| Punch-in          | ✅   | ✅   | both           | Server-side splice                     |
| Tracks            | ✅   | ✅   | both           | Custom names, colors, reorder          |
| Mixing            | ✅   | ✅   | both           | Volume, pan, EQ, comp, reverb, fades   |
| Master bus        | ✅   | ✅   | `screen.js`    | Limiter + meter                        |
| Timeline          | ✅   | ✅   | `screen.js`    | Waveforms + markers                    |
| Export            | ✅   | ✅   | `routes.py`    | ffmpeg pipeline                        |
| Demucs            | ✅   | ✅   | both           | Remote service, configurable           |
| Undo              | ✅   | ✅   | `screen.js`    | Debounced, capped                      |
| Tests             | ❌   | ❌   | —              | None automated                         |

## Drift

- README claims "convolution reverb with a generated 2-second room impulse
  response" — `_createReverbBus` in `screen.js` matches.
- README claims "Undo up to 50 steps" — `MAX_UNDO = 50` matches.
- README claims "Drift correction for >0.05%" — server pipeline matches.
- README mentions "EQ (Low Shelf 200Hz, Mid Peak 1kHz, High Shelf 4kHz)" —
  the EQ frequencies are baked into `screen.js` and should be cross-checked
  against the ffmpeg filter graph used for export to ensure §I.
- README header says "collaborative band recording" — collaboration here is
  asynchronous (file sharing across users). No live multi-user editing.
  Consider re-wording to avoid raising expectations.

## Gaps

1. **Mix equivalence not verified.** Constitution §I asks for parity between
   the Web Audio preview and the ffmpeg export. There is no automated golden
   render test today. Subtle filter-coefficient differences (Q-factor
   defaults, attack-curve shapes) can drift over time.
2. **No ffmpeg detection.** Missing ffmpeg surfaces as a 500 with a
   subprocess error (Q10). A startup probe would catch this.
3. **No optimistic concurrency on mix changes.** Two clients editing the same
   session race silently (Q11).
4. **No automated tests** — large Python + large JS surface, manual
   regression only.
5. **Demucs progress is opaque.** Long extractions appear to hang; only
   completion is signalled.
6. **No FLAC/AAC import.** Plausible asks, currently rejected.
7. **No stem export.** "Export" is mixed-down only.
8. **Soft-delete missing.** A misclick on Delete is unrecoverable.

## Recommendations

- **Add a golden-render test** that takes a small fixture session, exports
  via ffmpeg, runs the Web Audio graph through `OfflineAudioContext`, and
  compares the two waveforms below a perceptual threshold. Even a spot-check
  shrinks the §I risk significantly.
- **Probe ffmpeg/ffprobe at startup** (e.g. inside `_get_db` or a separate
  bootstrap), surface a clear "ffmpeg required" banner if missing.
- **Add a `mtime` / `version` column** to `studio_mix_settings` and reject
  POSTs with an outdated stamp; UI shows a soft "session updated by another
  client" toast.
- **Stream Demucs progress** via SSE or websocket so the UI shows percent
  complete instead of a spinner.
- **Add stem export** as a ZIP of per-track WAVs with the same per-track
  processing already applied (still mixed-down to a single channel).
- **Implement soft delete** by toggling an `is_archived` column; surface an
  archive view and a "delete forever" path.
- **Document the EQ / compressor frequency math** somewhere both `routes.py`
  and `screen.js` can reference, so the parity claim has a single source of
  truth.
