# Tasks — Base Game Song Extractor

Status legend: **DONE** = shipped in v1.0.0; **OPEN** = candidate work. `[P]` = parallel-safe.

## US1 — Extract all base-game songs

- **DONE** Read `songs.psarc` manifests and group by SongKey — `routes.py:64-90`
- **DONE** PSARC repack engine producing valid per-song PSARCs — `disc_extractor.py` (entire file)
- **DONE** WebSocket extract route streaming progress — `routes.py` (search `@app.websocket`)
- **DONE** Status endpoint returning per-song extracted flag — `routes.py:44-100`
- **DONE** UI rendering of status + per-song list — `screen.js:19-95`

## US2 — Skip already-extracted songs

- **DONE** Per-song extracted check on output dir — `routes.py:_check_extracted` style, surfaced in status payload
- **DONE** Action button text reflects remaining count — `screen.js:68-75`
- **DONE** "All Extracted" terminal state — `screen.js:73`

## US3 — Real-time progress

- **DONE** WebSocket frame schema (`progress`, `stage`, `done`, `error`) — `screen.js:105-130`
- **DONE** Progress bar + stage label rendering — `screen.html`, `screen.js:107-110`
- **OPEN** [P] Resume-friendly client: on WS error, auto-refresh status to reflect on-disk state instead of just showing "Connection lost" — `screen.js:132-134`

## US4 — Missing source file UX

- **DONE** Yellow "songs.psarc not found" card — `screen.js:36-44`
- **DONE** RS-dir auto-discovery from Docker mount + DLC parent + Steam paths — `routes.py:17-35`

## Cross-cutting

- **DONE** Idempotent `showScreen` wrap — `screen.js:3-17`
- **DONE** Library auto-cache via `extract_meta` + `meta_db` — `routes.py:38-42`
- **OPEN** [P] Add a "extract single song" affordance per row (currently only batch)
- **OPEN** [P] Surface SongKey alongside Title/Artist for advanced users debugging duplicates
- **OPEN** Verify DD preservation across extraction (clarify Q5)
- **OPEN** Test coverage: a fixture `songs.psarc` (or a tiny synthetic one) feeding `disc_extractor` end-to-end. None today.

## Documentation

- **DONE** README with Docker mount snippet
- **OPEN** [P] CHANGELOG / version history
- **OPEN** [P] Troubleshooting section (e.g. permission errors writing to DLC dir)
