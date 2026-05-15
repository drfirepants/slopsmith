# Feature Specification: Practice Journal

**Plugin id**: `practice_journal` (`plugin.json:2`)
**Nav**: "Practice" (`plugin.json:6`)
**Status**: Shipped (v1.0.0)

## Summary

Automatically tracks every practice session: which song, which arrangement,
how long, what speed, which loops were used. Surfaces an aggregate
dashboard (today / week / total), a 30-day activity bar chart, top-played
songs, and recent sessions.

## User Stories

### US-1 — Practice happens, the journal records it
**As** a guitarist using Slopsmith
**I want** my practice time logged automatically
**So that** I can see how much I actually practice without remembering
to start/stop a timer.

- **Given** the user has the plugin installed and opens any song
- **When** `playSong(filename, arrangement)` runs
- **Then** the wrapped function (`screen.js:26-38`) captures
  `_pjSessionStart`, `_pjFilename`, `_pjTitle`, `_pjArtist`,
  `_pjArrangement`, and resets `_pjSpeeds = [1.0]`,
  `_pjLoopsUsed = new Set()`.
- **And When** the user leaves the player (any `showScreen(id)` where
  `id !== 'player'`) or unloads the page
- **Then** `_pjEndSession()` posts the session to
  `/api/plugins/practice_journal/session` with `duration` (seconds),
  `avg_speed`, `loops_used`, etc.
- **And** sessions where `duration < 5` are dropped server-side
  (`routes.py:57-58`).

### US-2 — Dashboard shows progress at a glance
**As** the same user
**I want** a dashboard showing today, this week, total, song count,
and a 30-day chart
**So that** I can see trends.

- **Given** there is at least one logged session
- **When** the user navigates to `plugin-practice_journal`
- **Then** `_pjLoadDashboard()` (`screen.js:111`) calls
  `/api/plugins/practice_journal/stats` and populates `#pj-today`,
  `#pj-week`, `#pj-total`, `#pj-songs`, `#pj-chart`, `#pj-top`,
  `#pj-recent`.
- **And** the chart fills missing days with empty bars
  (`screen.js:130-138`).

### US-3 — Speed and loop awareness
**As** a learner
**I want** the journal to record what speed I practiced at and which
saved loops I used
**So that** I can see whether I'm still drilling 60% or have moved up.

- **Given** the user adjusts speed via the host's `setSpeed(v)` slider
- **When** the wrapped function runs (`screen.js:50-53`)
- **Then** `_pjSpeeds.push(parseFloat(v))` records each change.
- **And When** `loadSavedLoop(loopId)` runs (`screen.js:57-64`)
- **Then** the loop's display name (split on `(`) is added to
  `_pjLoopsUsed`.
- **And** `_pjEndSession()` averages speeds and serializes loops
  before POSTing.

### US-4 — Per-song history (API only)
**As** a power user or another plugin
**I want** to GET `/api/plugins/practice_journal/song/{filename}`
**So that** I can show per-song speed progression and last 50 sessions.
- *Note*: the dashboard does not currently call this endpoint;
  `routes.py:147-187` exposes it for future use.

## Functional Requirements

- **FR-1** Session row schema (`routes.py:19-31`):
  `(id PK, filename TEXT, title, artist, started_at, duration_seconds,
  avg_speed, loops_used JSON, arrangement)`.
- **FR-2** Indexes on `filename` and `started_at` (`routes.py:32-39`).
- **FR-3** Server drops sessions under 5 seconds.
- **FR-4** Frontend hooks are installed exactly once via
  `__slopsmithPracticeHooksInstalled` guard.
- **FR-5** `_pjEndSession` is also fired on `beforeunload`
  (`screen.js:99`).
- **FR-6** `/stats` returns `total_time`, `today_time`, `week_time`,
  `total_sessions`, `unique_songs`, `top_songs[≤10]`, `daily[≤30]`,
  `recent[≤20]`.
- **FR-7** `/song/{filename:path}` returns `total_time`,
  `session_count`, `speed_history[]`, `sessions[≤50]`.
- **FR-8** Network failures on POST `/session` MUST NOT throw to
  the user (`screen.js:91`).

## Non-Functional Requirements

- **NFR-1** SQLite WAL mode for concurrent reader safety
  (`routes.py:18`).
- **NFR-2** All writes guarded by `_lock` (`routes.py:8`).
- **NFR-3** Fire-and-forget POST — no retry logic, no offline queue.
- **NFR-4** No PII beyond what core already stores (filename, title,
  artist).

## Out of Scope

- Manual session editing or deletion [NEEDS CLARIFICATION: should
  there be a "delete session" UI? Currently impossible without DB
  access].
- Goals / streaks / gamification.
- Sync to a remote server.
- Per-arrangement aggregation in the dashboard (top_songs is keyed by
  filename, not by arrangement).

## Key Entities

- **Session**: one row in `practice_sessions` representing a
  contiguous in-player period.
- **Speed sample**: each call to `setSpeed`; averaged to one float
  per session.
- **Loop usage**: set of loop display names activated during the session.
