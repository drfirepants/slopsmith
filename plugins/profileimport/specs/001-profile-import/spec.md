# Feature Specification: Profile Import

**Plugin id**: `profileimport` (`plugin.json:2`)
**Nav**: "Profile Import" (`plugin.json:6`)
**Status**: Shipped (v1.0.0)

## Summary

Imports an encrypted Rocksmith 2014 player profile (`*_prfldb`) into
Slopsmith. Recovers favorites, play counts, mastery, accuracy, last
played dates, and Score Attack high scores/badges. Seeds the Practice
Journal plugin with synthetic sessions backfilled from play history.

## User Stories

### US-1 — Upload and preview a profile
**As** a returning Rocksmith 2014 player
**I want** to drop my `_prfldb` file into Slopsmith
**So that** I see exactly what's in it before committing.

- **Given** the user is on the Profile Import screen
- **When** they drag a `_prfldb` file onto `#pi-dropzone`
  (`screen.js:42-47`) or click to browse
- **Then** the file is sent as raw octet-stream to
  `POST /api/plugins/profileimport/upload` with `X-Filename` header
  (`screen.js:62-67`)
- **And** the server decrypts it (`decrypt_profile` at
  `routes.py:59-94`) and returns a summary:
  arrangements played/mastered, favorites count, score attack, total
  play count, sessions, session time, song lists.
- **And** the plain-text profile is stashed in
  `_stashed_profiles[profile_id]` (`routes.py:153-155`).

### US-2 — Build the SongKey mapping cache
**As** the same user
**I want** Slopsmith to map the profile's `PersistentID`s and
`SongKey`s to local PSARC filenames
**So that** the import knows which song each play count belongs to.

- **Given** the user has uploaded a profile
- **When** they click `#pi-build-mapping-btn`
- **Then** a WebSocket connects to
  `/ws/plugins/profileimport/build-mapping` (`screen.js:140-141`)
- **And** the server walks every `*.psarc` in the DLC dir, parses
  manifest JSONs, and populates `songkey_map(persistent_id, song_key,
  filename, arrangement)` excluding Vocals (`routes.py:266-300`).
- **And** progress messages stream every 100 PSARCs and at completion.

### US-3 — Run the import
**As** the same user
**I want** to choose which categories to import (favorites / play
counts / Score Attack)
**So that** I can scope the migration.

- **Given** the user has built the mapping (`cached_mappings > 0`)
- **When** they tick the desired checkboxes and click `#pi-import-btn`
- **Then** a WebSocket to `/ws/plugins/profileimport/import`
  is opened with `{profile_id, import_favorites, import_play_counts,
  import_scores}`.
- **And** server stages emit progress: `favorites` → `playcounts` →
  `scores` → `complete` (`routes.py:335-601`).
- **And** matched favorites are toggled via
  `_meta_db.toggle_favorite(filename)`.
- **And** play counts populate `play_stats` and seed synthetic rows in
  `practice_journal.db.practice_sessions` for matched filenames.
- **And** Score Attack data populates `score_attack` (per-difficulty
  high scores + badges).

### US-4 — Review past imports
**As** an admin user
**I want** to see when imports ran and what they brought in
**So that** I can audit the history.

- **Given** at least one import has completed
- **When** the user views the page or after `_piShowDone`
- **Then** `GET /api/plugins/profileimport/history` returns the last 20
  imports (`routes.py:206-219`).

## Functional Requirements

- **FR-1** Decrypt EVAS profile: 4-byte magic `EVAS`, 4-byte version,
  8-byte profile_id, 4-byte uncompressed_len, AES-256-ECB +
  zlib decompress (`routes.py:69-93`).
- **FR-2** `POST /upload` returns `{header, filename,
  total_arrangements_tracked, arrangements_played, arrangements_mastered,
  total_play_count, favorites_count, song_lists_count,
  score_attack_played, total_sessions, total_session_time}`.
- **FR-3** `GET /mapping-status` returns `{cached_mappings: int}`.
- **FR-4** `WS /build-mapping` streams `{stage, total, progress, errors}`
  during scan and `{stage: "done", mappings, errors}` at the end.
- **FR-5** `WS /import` accepts `{profile_id, import_*: bool}` and
  streams `{stage, message, progress?, total?, matched?, done?}`
  per stage and `{stage: "complete", stats}` at the end.
- **FR-6** Favorites import only adds; never removes existing favorites
  (`routes.py:339-358`).
- **FR-7** Play-count import creates one synthetic
  `practice_sessions` row per matched (filename, last-played) pair
  with duration `play_count * min(song_duration, 600)` and `avg_speed=1.0`
  (`routes.py:434-452`).
- **FR-8** Score Attack import populates per-difficulty high score and
  badge columns (`routes.py:512-577`).
- **FR-9** All long-running writes batched in chunks of 500 with
  `INSERT OR REPLACE` and yielding to the loop
  (`routes.py:454-481`).
- **FR-10** `import_history` row written at end of import
  (`routes.py:585-594`).

## Out of Scope

- Cloud profile sync.
- Importing tone library or custom tunings from the profile.
- Removing favorites that are no longer favorites in the profile
  [NEEDS CLARIFICATION: bidirectional sync intentionally absent].
- Re-running import incrementally (delta) — current flow is full re-import.

## Key Entities

- **Profile**: decrypted JSON; key sub-trees `Stats.Songs`,
  `FavoritesListRoot.FavoritesList`, `SongsSA`, `SongListsRoot.SongLists`.
- **SongKey mapping**: `(persistent_id, song_key, filename, arrangement)`
  built once per DLC folder.
- **play_stats**: per-arrangement aggregate of plays/mastery/accuracy.
- **score_attack**: per-arrangement per-difficulty SA results.
- **import_history**: audit trail.
