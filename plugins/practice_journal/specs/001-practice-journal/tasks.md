# Tasks — Practice Journal

## US-1: Auto-recording

- [x] **DONE** Wrap `playSong` to start a session (`screen.js:26-38`).
- [x] **DONE** Wrap `showScreen` to end on player exit (`screen.js:42-46`).
- [x] **DONE** `beforeunload` listener (`screen.js:99`).
- [x] **DONE** Server drops <5s sessions (`routes.py:57-58`).
- [x] **DONE** Idempotency guard `__slopsmithPracticeHooksInstalled`
  (`screen.js:20-22`).
- [x] **DONE** Fire-and-forget POST (`screen.js:79-92`).

## US-2: Dashboard

- [x] **DONE** `_pjLoadDashboard` fetches `/stats` and renders.
- [x] **DONE** 30-day bar chart with missing-day backfill
  (`screen.js:128-148`).
- [x] **DONE** Top songs (max 10) with width-pct bar.
- [x] **DONE** Recent sessions (max 20).
- [ ] **OPEN [P]** Add a "longest streak" tile.
- [ ] **OPEN [P]** Show speed trend per song using
  `/song/{filename}/speed_history`.

## US-3: Speed + loop tracking

- [x] **DONE** Wrap `setSpeed` to push samples (`screen.js:50-53`).
- [x] **DONE** Wrap `loadSavedLoop` to capture display name
  (`screen.js:57-64`).
- [x] **DONE** Average speeds in `_pjEndSession` (`screen.js:74-76`).
- [x] **DONE** Persist loops as JSON (`routes.py:73`).
- [ ] **OPEN** Switch loop tracking from name to stable ID
  (clarify Q7).

## US-4: Per-song history endpoint

- [x] **DONE** Endpoint exists (`routes.py:147-187`).
- [ ] **OPEN** Wire it into a per-song detail view.

## Schema / DB

- [x] **DONE** Schema + indexes created on first connection
  (`routes.py:19-39`).
- [x] **DONE** WAL mode enabled (`routes.py:18`).
- [x] **DONE** Lock around all writes.
- [ ] **OPEN [P]** Document migration policy for future schema
  changes (constitution §V).

## Cross-plugin

- [x] **DONE** Profileimport writes synthetic sessions into the same DB.
- [ ] **OPEN [P]** Add a regression test that profileimport's row
  shape matches our schema.

## Spec-kit hygiene

- [x] **DONE** Constitution authored.
- [x] **DONE** Spec / clarify / plan / tasks / analyze under
  `specs/001-practice-journal/`.
