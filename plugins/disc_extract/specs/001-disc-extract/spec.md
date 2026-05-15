# Feature Specification: Base Game Song Extractor

**Plugin id**: `disc_extract` (per `plugin.json`)
**Status**: Shipped (v1.0.0)
**Type**: Screen + backend routes (FastAPI + WebSocket)

## Summary

Slopsmith plugin that splits Rocksmith 2014's `songs.psarc` into individual per-song CDLC PSARCs and drops them into the configured DLC directory so Slopsmith treats them as ordinary songs.

## User Stories

### US1 — Extract all base-game songs (Priority: P1)
As a Rocksmith 2014 owner, I want to extract the on-disc songs into Slopsmith's library so I can play them alongside my CDLC.

**Given** my Rocksmith install is mounted at `/rocksmith` (or autodiscovered next to my DLC dir),
**When** I open the "Base Game Extract" screen and click "Extract All",
**Then** each song in `songs.psarc` is written as `{Title} - {Artist}_p.psarc` to my DLC directory and indexed in the Slopsmith library.

### US2 — Skip already-extracted songs (Priority: P1)
As a user re-running the extractor, I don't want duplicates or re-work.

**Given** some songs are already extracted on disk,
**When** I open the screen,
**Then** the song list marks those as "extracted", and the action button reads "Extract N Remaining" (or "All Extracted" with no button).

### US3 — Watch progress in real time (Priority: P2)
As a user running a long extraction, I want live feedback.

**Given** an extraction is in progress,
**When** the WebSocket emits stage/progress events,
**Then** the UI shows a progress bar and the current stage text; on `done` it shows a success card with the count, on `error` a failure card with the message.

### US4 — Handle missing source file (Priority: P2)
As a user without a Rocksmith install mounted, I want a clear hint, not a stack trace.

**Given** `songs.psarc` cannot be located,
**When** I open the screen,
**Then** I see a yellow warning card explaining that `Rocksmith2014` must be mounted at `/rocksmith` in Docker.

## Functional Requirements

- **FR1**: `GET /api/plugins/disc_extract/status` MUST return `{has_songs_psarc, rs_dir, song_count, extracted_count, songs[]}`. Each song entry includes `key, title, artist, arrangements[], extracted` flag.
- **FR2**: `WS /ws/plugins/disc_extract/extract` MUST stream `{progress, stage, done?, total?, error?}` JSON frames per song processed.
- **FR3**: PSARC writer MUST include SNG, manifests, album art, audio (BNK + WEM), showlights, xblock, and produce a valid aggregate graph + per-song HSAN.
- **FR4**: Vocals / ShowLights / JVocals arrangements MUST be excluded from the per-song listing (they're packed alongside playable arrangements, not as standalone titles).
- **FR5**: After write, the plugin MUST call core's `extract_meta` + `meta_db` to register the new PSARC without a Slopsmith restart.
- **FR6**: `screen.js` MUST be idempotent against re-evaluation (hook guard installed; no chained `showScreen` wrappers).
- **FR7**: Filename collisions MUST be deterministic — if a `_p.psarc` matching the song already exists, skip extraction for that song.

## Non-Functional Requirements

- The Docker mount of `/rocksmith` is `:ro`; the plugin MUST NOT attempt to write to it.
- WebSocket disconnect during extraction MUST NOT abort server-side work (it's a streaming progress channel only). [NEEDS CLARIFICATION: confirm in `routes.py` — current behaviour vs requirement]

## Out of Scope

- Editing or repacking arrangements (that's the editor plugin).
- Extracting per-arrangement subsets (only whole-song extraction).
- Anything outside `songs.psarc` (DLC files, song packs, etc.).
