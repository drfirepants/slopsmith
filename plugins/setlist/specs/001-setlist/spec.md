# Feature Specification: Setlist Builder

**Plugin id**: `setlist` (`plugin.json:2`)
**Nav**: "Setlists" (`plugin.json:6`)
**Status**: Shipped (v1.0.0)

## Summary

Create ordered playlists ("setlists") of songs for gig prep, practice
routines, or themed sessions. Each entry can be pinned to a specific
arrangement (Lead / Rhythm / Bass / Vocals). A "Play All" button steps
through them sequentially with auto-advance.

## User Stories

### US-1 — Create and manage setlists
**As** a guitarist preparing for a gig
**I want** to create a named setlist
**So that** I can group the songs I'll be playing.

- **Given** the user is on the Setlists screen
- **When** they click "New" and enter a name (`screen.js:32-41`)
- **Then** `POST /api/plugins/setlist/create` creates a row and
  the list reloads.
- **And** the user can rename via `POST /{id}/rename`
  (`routes.py:82-92`) and delete via `DELETE /{id}`
  (`routes.py:73-80`).

### US-2 — Add songs with chosen arrangement
**As** the same user
**I want** to search the library and add a song to a chosen slot
**So that** the setlist tells me which arrangement to play.

- **Given** the user is in a setlist's detail view
- **When** they type into `#sl-search` and trigger
  `slSearchSongs` (`screen.js:134-157`)
- **Then** the host library is queried via
  `/api/library?q=...&page=0&size=10&sort=artist`.
- **And** each result row offers one button per arrangement.
- **And When** the user clicks an arrangement button
- **Then** `POST /{id}/add` appends the song with that arrangement
  (`routes.py:118-139`).

### US-3 — Reorder and remove
**As** the same user
**I want** up/down arrows on each row to reorder
**So that** I can curate the flow.

- **Given** a setlist with ≥2 songs
- **When** the user clicks ▲ or ▼ on a song
- **Then** `slMove` (`screen.js:114-130`) fetches current order,
  swaps, posts to `/{id}/reorder`.
- **And** clicking ✕ posts `DELETE /{id}/song/{song_id}` which
  re-numbers all positions densely (`routes.py:141-156`).

### US-4 — Play All with auto-advance
**As** the same user practicing the gig
**I want** to play through the setlist hands-free
**So that** I focus on playing, not clicking.

- **Given** a setlist with ≥1 song
- **When** the user clicks "Play All"
- **Then** `slPlayAll` (`screen.js:173-181`) loads the songs into
  `_slQueue`, sets `_slQueueIndex=0`, and starts via `_slPlayCurrent`.
- **And** the floating progress overlay shows
  `Setlist: i / N`, current title/artist, and Prev/Next/Stop buttons
  (`screen.js:196-215`).
- **And When** the host `<audio>` fires `ended`
- **Then** the listener (`screen.js:243-249`) advances via `_slNext`
  while a queue is active.
- **And** Next on the last song calls `_slStopQueue` and removes the
  overlay.

## Functional Requirements

- **FR-1** Schema (`routes.py:18-37`):
  `setlists(id PK, name, created_at, updated_at)` and
  `setlist_songs(id PK, setlist_id FK, filename, title, artist,
   position, arrangement)`.
- **FR-2** `GET /list` returns each setlist with `song_count`
  computed via correlated subquery.
- **FR-3** `POST /create` requires non-empty `name`; trims; returns
  `{id, name}`.
- **FR-4** `DELETE /{setlist_id}` removes setlist + cascade.
- **FR-5** `POST /{setlist_id}/rename` requires non-empty `name`.
- **FR-6** `GET /{setlist_id}` returns `{id, name, created_at,
  songs[]}` ordered by position.
- **FR-7** `POST /{setlist_id}/add` appends at `MAX(position)+1`,
  bumps `setlists.updated_at`.
- **FR-8** `DELETE /{setlist_id}/song/{song_id}` removes and
  re-numbers densely.
- **FR-9** `POST /{setlist_id}/reorder` accepts `{song_ids: [...]}`
  and assigns 1-based positions in that order.
- **FR-10** Frontend `audio.ended` listener auto-advances.

## Non-Functional Requirements

- **NFR-1** SQLite WAL with module-level lock for writes.
- **NFR-2** No per-user partitioning — all setlists are global to the
  Slopsmith instance.

## Out of Scope

- Sharing / export of setlists [NEEDS CLARIFICATION].
- Tags / categories.
- Duration estimates per setlist.
- Drag-and-drop reordering [NEEDS CLARIFICATION: arrows only today].
- Conflict UI for songs whose arrangement was deleted from the
  source PSARC [NEEDS CLARIFICATION].

## Key Entities

- **Setlist**: `{id, name, created_at, updated_at, song_count}`.
- **SetlistSong**: `{id, setlist_id, filename, title, artist,
  position, arrangement}`.
