# Tasks — Profile Import

## US-1: Upload and preview

- [x] **DONE** Drag-drop + click-to-browse on `#pi-dropzone`
  (`screen.js:30-53`).
- [x] **DONE** `POST /upload` accepts raw octet-stream + `X-Filename`
  header (`routes.py:133-156`).
- [x] **DONE** `decrypt_profile` validates magic, version, lengths
  (`routes.py:59-94`).
- [x] **DONE** Stash decrypted profile by `profile_id`
  (`routes.py:153-155`).
- [x] **DONE** Preview UI populates stats grid + extras line
  (`screen.js:84-104`).
- [ ] **OPEN [P]** Add a TTL/eviction sweep for `_stashed_profiles`
  (clarify Q3).

## US-2: SongKey mapping

- [x] **DONE** `GET /mapping-status` (`routes.py:158-163`).
- [x] **DONE** `WS /build-mapping` walks DLC dir, parses manifests
  (`routes.py:165-178`, `_build_mapping` 242-318).
- [x] **DONE** Skip Vocals (`routes.py:275`).
- [x] **DONE** Batch INSERT OR REPLACE every 100 PSARCs.
- [x] **DONE** Yield to loop with `asyncio.sleep(0)` (line 299).
- [ ] **OPEN [P]** Add an "incremental rebuild" that only scans new
  PSARCs since last build.

## US-3: Import

- [x] **DONE** `WS /import` accepts options + dispatches stages
  (`routes.py:180-204`).
- [x] **DONE** Favorites: only adds (`routes.py:339-358`).
- [x] **DONE** Play counts populate `play_stats` and seed
  `practice_journal.db` synthetic sessions.
- [x] **DONE** Score Attack populates `score_attack`.
- [x] **DONE** Insert `import_history` row at completion.
- [x] **DONE** Evict stashed profile after import.
- [ ] **OPEN** Server-side mutex preventing concurrent imports
  (clarify Q9).
- [ ] **OPEN [P]** Honor `import_play_counts=false` without still
  computing play_counts queries (today the WS still walks the dict).

## US-4: History

- [x] **DONE** `GET /history` returns last 20 (`routes.py:206-219`).
- [x] **DONE** Frontend lists with time + counts (`screen.js:290-317`).
- [ ] **OPEN [P]** Add per-row "delete" / "view diff" actions.

## Auxiliary

- [x] **DONE** `GET /play-stats` for library overlay (`routes.py:221-235`).
- [ ] **OPEN** Wire `/play-stats` into a library overlay UI
  (currently only the data is exposed).
- [ ] **OPEN [P]** Materialize `SongLists` into setlist plugin via API
  (clarify Q7).

## Schema

- [x] **DONE** `songkey_map` + indexes.
- [x] **DONE** `import_history`.
- [x] **DONE** `play_stats` + index (lazy).
- [x] **DONE** `score_attack` + index (lazy).
- [ ] **OPEN [P]** Centralize `practice_sessions` schema with
  practice_journal plugin (constitution §V).

## Spec-kit hygiene

- [x] **DONE** Constitution.
- [x] **DONE** Spec / clarify / plan / tasks / analyze.
