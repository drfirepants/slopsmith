# Implementation Plan — Practice Journal

## Architecture

```
slopsmith-plugin-practice/
├── plugin.json    — id=practice_journal, nav, screen, script, routes
├── routes.py      — FastAPI routes + sqlite3 store
├── screen.html    — dashboard markup (hosts pj-* element ids)
├── screen.js      — host hooks + dashboard rendering
└── README.md      — user-facing description
```

Backend: SQLite (WAL) at `${config_dir}/practice_journal.db` with one
table `practice_sessions` and two indexes.

Frontend: a single IIFE wrapping four host globals plus a
`_pjLoadDashboard` triggered when the user navigates to the plugin
screen.

## Backend modules (`routes.py`)

| Symbol | Lines | Purpose |
|--------|-------|---------|
| `_get_conn()` | 14-41 | Lazy-open SQLite, create schema, set WAL |
| `setup(app, context)` | 44 | Plugin entry point per core contract |
| `POST /session` | 49-78 | Record one session; drop <5s |
| `GET /stats` | 80-145 | Aggregate dashboard payload |
| `GET /song/{filename:path}` | 147-187 | Per-song detail (unused by UI today) |

State: module-level `_db_path`, `_conn`, `_lock = threading.Lock()`.
The lock guards every write; reads piggy-back on WAL.

## Frontend modules (`screen.js`)

### Host hooks (lines 15-65)
Wrapped under one `__slopsmithPracticeHooksInstalled` guard:
- `playSong`: ends previous session → awaits original →
  initializes session state.
- `showScreen`: ends session if leaving player; if entering the
  plugin screen, calls `_pjLoadDashboard()`.
- `setSpeed`: appends to `_pjSpeeds`.
- `loadSavedLoop`: appends parsed display name to `_pjLoopsUsed`.

### Session lifecycle (lines 67-99)
- `_pjEndSession()`: computes duration + avg speed, fires-and-forgets
  POST, nulls session state.
- `beforeunload`: also fires `_pjEndSession`.

### Dashboard (lines 101-198)
- `_pjFormatDuration(s)` — `s/m/h m` formatting.
- `_pjLoadDashboard()` — fetch `/stats`, render four stat cards,
  30-day bar chart with missing days backfilled, top-songs list with
  per-row width-pct bar, recent sessions list.

## Database schema

```sql
CREATE TABLE practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    started_at TEXT NOT NULL,   -- ISO-8601 UTC
    duration_seconds REAL NOT NULL DEFAULT 0,
    avg_speed REAL NOT NULL DEFAULT 1.0,
    loops_used TEXT DEFAULT '[]',  -- JSON array of strings
    arrangement TEXT
);
CREATE INDEX idx_practice_filename ON practice_sessions(filename);
CREATE INDEX idx_practice_started  ON practice_sessions(started_at);
```

## Cross-plugin contract

`profileimport` writes synthetic rows directly via its own
`sqlite3.connect(${config_dir}/practice_journal.db)` (see
profileimport `routes.py:387-405`). Any schema change here MUST be
mirrored there.

## Risks

| Risk | Mitigation |
|------|-----------|
| Re-evaluation of `screen.js` re-wraps host globals | `__slopsmithPracticeHooksInstalled` guard |
| User closes tab mid-session | `beforeunload` listener |
| Network drops POST | Fire-and-forget; session lost (acceptable) |
| Schema drift across plugins | Constitution §V — profileimport must follow |
| UTC date-boundary anomaly | Documented in clarify Q3 |

## Open items

- Local-time aggregation [NEEDS CLARIFICATION].
- Stable loop identity vs display-name matching [NEEDS CLARIFICATION].
- UI for editing/deleting sessions [NEEDS CLARIFICATION].
