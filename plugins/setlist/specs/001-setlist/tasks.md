# Tasks — Setlist Builder

## US-1: Setlist CRUD

- [x] **DONE** Schema (`routes.py:18-37`).
- [x] **DONE** `GET /list` with song count.
- [x] **DONE** `POST /create` with name validation.
- [x] **DONE** `DELETE /{id}` with cascade.
- [x] **DONE** `POST /{id}/rename`.
- [x] **DONE** Frontend list with Create / Delete buttons.
- [ ] **OPEN [P]** Replace `prompt()` calls with a host-provided modal
  (clarify Q3).

## US-2: Add songs with arrangement

- [x] **DONE** Library search (`/api/library?q=...`).
- [x] **DONE** Per-arrangement "+" buttons in results
  (`screen.js:148-154`).
- [x] **DONE** `POST /{id}/add` denormalized columns.
- [ ] **OPEN [P]** Allow adding without an arrangement (currently the
  UI requires picking one).

## US-3: Reorder / remove

- [x] **DONE** Up/down arrows trigger `/reorder`.
- [x] **DONE** ✕ removes and renumbers densely.
- [ ] **OPEN** Drag-and-drop reorder.
- [ ] **OPEN** Validate `song_ids[]` length matches setlist size
  (clarify Q2).

## US-4: Play All

- [x] **DONE** `slPlayAll` loads queue and starts playback.
- [x] **DONE** Floating overlay with prev/next/stop.
- [x] **DONE** `audio.ended` auto-advance.
- [ ] **OPEN** Move the `audio.ended` listener inside
  `__slopsmithSetlistHooksInstalled` guard (clarify Q5).
- [ ] **OPEN [P]** Show countdown to next song / break time between
  songs.

## Robustness / housekeeping

- [x] **DONE** Idempotent `showScreen` wrap.
- [x] **DONE** WAL + lock around writes.
- [ ] **OPEN [P]** Surface broken filename references in detail view
  (clarify Q1 of "out of scope").
- [ ] **OPEN [P]** Add a "duplicate setlist" action.

## Spec-kit hygiene

- [x] **DONE** Constitution.
- [x] **DONE** Spec / clarify / plan / tasks / analyze.
