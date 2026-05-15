# Implementation Plan — Setlist Builder

## Architecture

```
slopsmith-plugin-setlist/
├── plugin.json
├── routes.py    — REST CRUD over SQLite
├── screen.html  — list + detail views (one screen, two `.hidden` panels)
├── screen.js    — list/detail rendering, search, queue playback
└── README.md
```

## Backend (`routes.py`, 174 lines)

### Schema
```sql
CREATE TABLE setlists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE setlist_songs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  setlist_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  title TEXT,
  artist TEXT,
  position INTEGER NOT NULL,
  arrangement TEXT,
  FOREIGN KEY (setlist_id) REFERENCES setlists(id) ON DELETE CASCADE
);
```
DB at `${config_dir}/setlists.db`, WAL.

### Endpoints
| Method | Path | Function | Notes |
|--------|------|----------|-------|
| GET | `/list` | `list_setlists` | Includes `song_count` subquery |
| POST | `/create` | `create_setlist` | Trims & validates name |
| DELETE | `/{id}` | `delete_setlist` | Explicit cascade |
| POST | `/{id}/rename` | `rename_setlist` | Bumps `updated_at` |
| GET | `/{id}` | `get_setlist` | Songs ordered by position |
| POST | `/{id}/add` | `add_to_setlist` | `MAX(pos)+1` insert |
| DELETE | `/{id}/song/{song_id}` | `remove_from_setlist` | Re-numbers densely |
| POST | `/{id}/reorder` | `reorder_setlist` | `{song_ids[]}` → 1-based positions |

All writes guarded by `_lock` and bump `setlists.updated_at`.

## Frontend (`screen.js`, 274 lines)

### State
```
_slCurrentId  — currently open setlist id, or null
_slQueue      — songs[] for Play All
_slQueueIndex — current playing index, or -1
```

### List view (lines 7-47)
- `slLoadList()` — fetches `/list` and renders rows.
- `slCreateNew()` — `prompt()` + POST `/create`.
- `slDelete(id, name)` — `confirm()` + DELETE.

### Detail view (lines 49-130)
- `slOpenDetail(id)` / `slBackToList()` — toggle `.hidden`.
- `slLoadDetail()` — render songs with up/down/✕ buttons.
- `slMove(songId, ±1)` — fetch order, swap, POST `/reorder`.
- `slRemoveSong(songId)` — DELETE.
- `slRename()` — `prompt()` + POST `/rename`.

### Add songs (lines 132-169)
- `slSearchSongs()` — query `/api/library?q=...`.
- `slAddSong(filename, title, artist, arrangement)` — POST `/add`.

### Play All (lines 171-238)
- `slPlayAll()` — load queue.
- `_slPlayCurrent()` — call `playSong(...)` and show overlay.
- `_slShowProgress()` — render the floating overlay.
- `_slNext` / `_slPrev` — index manipulation; Next on last → Stop.
- `_slStopQueue()` — remove overlay, reset queue state.

### Hooks (lines 240-273)
- `audio.ended` listener auto-advances if queue is active.
- `showScreen` wrap (under `__slopsmithSetlistHooksInstalled`)
  reloads the list view when opening `plugin-setlist`.

## Library search contract

Reads from the host endpoint `/api/library?q=...&page=0&size=10&sort=artist`.
Each song result is expected to include
`{filename, title, artist, arrangements: [{name}, ...]}`.

## Risks

| Risk | Mitigation |
|------|-----------|
| `audio.ended` listener leaks on re-eval | Move into idempotency guard (open task) |
| Reorder length mismatch | No validation today; trust client (clarify Q2) |
| Missing `esc` global | Assumes core ships it |
| Setlist references deleted song | Failure deferred to playSong invocation |

## Open items

- Drag-and-drop reorder [NEEDS CLARIFICATION].
- Broken-reference UI [NEEDS CLARIFICATION].
- Sharing / export [NEEDS CLARIFICATION].
- Move `audio.ended` listener under idempotency guard (clarify Q5).
