# Implementation Plan — Profile Import

## Architecture

```
slopsmith-plugin-profileimport/
├── plugin.json
├── routes.py     — decrypt + REST + WebSocket import flow
├── screen.html   — upload → preview → progress → done flow + history
└── screen.js     — drag-drop, WS clients, history rendering
```

External deps: `pycryptodome` (`Crypto.Cipher.AES`), `zlib` stdlib,
`fastapi`. The PSARC scan reuses `psarc.read_psarc_entries` from
slopsmith core's `lib/`.

## Backend (`routes.py`, 602 lines)

### Module state (lines 22-27)
- `_db_path`, `_conn`, `_lock` — plugin DB.
- `_meta_db`, `_get_dlc_dir`, `_config_dir` — bound from `context`.
- `_stashed_profiles: dict[str, dict]` — in-memory cache between
  upload and import.

### Schema (lines 30-56)
- `songkey_map(persistent_id PK, song_key, filename, arrangement)`
  + indexes on song_key and filename.
- `import_history(id, imported_at, profile_id, songs_matched,
  favorites_imported, play_counts_imported)`.
- `play_stats` (created on import, lines 369-384) and `score_attack`
  (lines 519-538) created lazily.

### Crypto (lines 59-94)
`decrypt_profile(data) -> (header, profile)`:
1. Verify `EVAS` magic.
2. Read version/profile_id/uncompressed_len.
3. AES-256-ECB on remainder with `PROFILE_KEY`.
4. zlib decompress, strip trailing NUL, parse JSON.

### Endpoints
- `POST /api/plugins/profileimport/upload` — raw bytes →
  decrypt + summary; stash in `_stashed_profiles`.
- `GET /api/plugins/profileimport/mapping-status` — count of cached
  mappings.
- `WS /ws/plugins/profileimport/build-mapping` — see `_build_mapping`
  (lines 242-318).
- `WS /ws/plugins/profileimport/import` — see `_do_import`
  (lines 321-601).
- `GET /api/plugins/profileimport/history` — last 20 imports.
- `GET /api/plugins/profileimport/play-stats` — top 100 by play_count
  (lines 221-235).

### `_build_mapping` (lines 242-318)
Walks every `*.psarc` in the DLC directory, reads every `*.json`
manifest, harvests `(PersistentID, SongKey, filename, ArrangementName)`
tuples (skipping Vocals), batches into chunks of 100 PSARCs,
`INSERT OR REPLACE` into `songkey_map`. Errors per PSARC are counted,
not raised.

### `_do_import` (lines 321-601)
1. **Favorites** — for each SongKey in `FavoritesList`, look up first
   matching filename, call `_meta_db.toggle_favorite` if not already
   favorited.
2. **Play counts** — for each `Stats.Songs[pid]`, look up
   (filename, song_key, arrangement), insert into `play_stats`, and
   build a synthetic `practice_sessions` row in `practice_journal.db`
   when filename + DateLAS are present.
3. **Score Attack** — for each `SongsSA[pid]` with PlayCount > 0,
   record per-difficulty high scores + badges in `score_attack`.
4. Insert one `import_history` row, evict stashed profile.

## Frontend (`screen.html` + `screen.js`)

### `screen.html`
Four sections gated by `.hidden` class:
- `#pi-upload-section` — dropzone + hidden file input.
- `#pi-preview-section` — stats grid + import option checkboxes +
  mapping status block + Import button.
- `#pi-progress-section` — staged log with per-stage progress bars.
- `#pi-done-section` — success card with Import Another / Back buttons.
Plus `#pi-history-section` (always visible).

### `screen.js` (327 lines)
- `_piInit` (line 24) — runs on `showScreen('plugin-profileimport')`.
- `_piUploadFile` (line 57) — POSTs raw bytes, shows preview.
- `_piCheckMapping` / `_piBuildMapping` — REST status + WS scan.
- `_piStartImport` (line 179) — WS import client, dispatches
  per-stage UI updates via `_piUpdateStage`.
- `_piLoadHistory` (line 290) — fetches and renders history rows.

Idempotency: `__slopsmithProfileImportHooksInstalled` (line 11) and
`dropzone._piInitialized` (line 32).

## Cross-plugin contract

Writes directly into `practice_journal.db`:
- Connects with `sqlite3.connect(${config_dir}/practice_journal.db)`.
- Re-creates schema (defensive against the plugin not being installed).
- Inserts via the same column shape as practice_journal's
  `record_session` route.

If the practice_journal plugin is **not** installed:
- Synthetic rows are written anyway. The DB file exists alone; the
  practice_journal plugin would pick them up if installed later.

## Risks

| Risk | Mitigation |
|------|-----------|
| Schema drift between this plugin and practice_journal | Coordinated bump |
| Concurrent imports (race on _meta_db) | Document serial use; future mutex |
| Stashed-profile memory leak | Eviction at end of import; restart clears |
| ECB cipher format requirement | Externally fixed |
| Large libraries blocking event loop | Yield with `asyncio.sleep(0)` per batch |

## Open items

- TTL on `_stashed_profiles` [NEEDS CLARIFICATION].
- Bidirectional favorites sync [NEEDS CLARIFICATION].
- Materializing song lists as setlists [NEEDS CLARIFICATION].
- Server-side import mutex [NEEDS CLARIFICATION].
