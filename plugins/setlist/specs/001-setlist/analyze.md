# Analyze — Setlist Builder

## Coverage

| Area | Code | Tests | Spec |
|------|------|-------|------|
| CRUD endpoints | `routes.py:48-92` | None | FR-2..5 |
| Detail / songs | `routes.py:94-156` | None | FR-6..8 |
| Reorder | `routes.py:158-173` | None | FR-9 |
| List/detail UI | `screen.js:9-130` | None | US-1, US-3 |
| Search/add | `screen.js:132-169` | None | US-2 |
| Play All | `screen.js:173-238` | None | US-4, FR-10 |

No tests, no CI workflow.

## Drift

1. **`audio.ended` listener** is registered in a bare IIFE outside the
   idempotency guard (`screen.js:241-250`). Re-evaluation grows the
   listener count; auto-advance fires multiple times per song end.
2. **`prompt()` and `confirm()`** are used for naming/deletion — at
   odds with the rest of the host's modal-based UX.
3. **Reorder validation gap**: a malicious client can pass arbitrary
   ids; mismatched-length payloads silently leave gaps in the
   ordering.
4. **Filename forward references**: deleting a song from the library
   leaves dangling rows; the UI surfaces them as clickable but
   broken.
5. **CLAUDE.md is the speckit stub**.

## Gaps

- No tests of any kind.
- No protection against a setlist with thousands of songs (UI lists
  unconditionally; pagination absent).
- No conflict resolution if two browser tabs reorder simultaneously
  (last write wins; not surfaced).
- No setlist export (JSON / CSV) for backup or sharing.
- No estimate of total setlist runtime.

## Recommendations

1. **Move the `audio.ended` listener inside the idempotency guard**
   to fix the multi-fire bug. One-line change.
2. **Validate `song_ids[]` length** against `COUNT(*)` for
   `setlist_id` and 400 on mismatch.
3. **Add a `/export` endpoint** returning JSON; trivial backup story.
4. **Replace `prompt()`** with the host's modal once available.
5. **Add basic tests**: schema creation idempotency, CRUD round-trip,
   reorder densification, cascade delete.
6. **Surface broken filenames**: cross-check against `meta_db` on
   `GET /{id}` and add a `broken: true` flag.
7. **Replace CLAUDE.md** with a spec-pointer.

## Risk assessment

- **Low–medium**: data is small, writes are serialized, but the
  duplicate-listener bug is a real correctness issue affecting any
  user who hot-reloads or re-opens the screen multiple times in a
  session.
