# Clarifications — Profile Import

## Q1: Why AES-256-ECB? ECB has known weaknesses.
**A**: The format is fixed by Rocksmith 2014. The plugin does not choose
the cipher; it must match the on-disk format. Plaintext is recovered to
JSON (`routes.py:80-88`).

## Q2: How are PersistentID and SongKey related?
**A**: Each Rocksmith arrangement has a `PersistentID` (per-arrangement
GUID, the key the profile uses) and a `SongKey` (the song-level
identifier, e.g. `BTGoldDust`). The mapping table records both because
favorites use SongKey and stats use PersistentID
(`routes.py:336-352` and `routes.py:411-422`).

## Q3: What happens if a profile is uploaded and the user navigates away
before importing?
**A**: `_stashed_profiles[profile_id]` lives in process memory. It
survives page reloads (because it's server-side) until the import runs
(removed at `routes.py:596`) or the server restarts. There is no TTL.
[NEEDS CLARIFICATION: should stashed profiles expire after N minutes?
Currently they leak until restart.]

## Q4: Why does the WebSocket protocol differ from REST?
**A**: Mapping scan and import can take minutes on large libraries.
Over REST, the request would either time out or block the client UI;
WebSocket lets the server emit progress every 100 PSARCs / 500 rows
without waiting for the next request.

## Q5: Why are vocals excluded from the mapping?
**A**: `routes.py:275` filters `arrangement != "Vocals"`. Vocals don't
appear in the profile's play counts/Score Attack data, so mapping
them would only bloat the cache.

## Q6: What is a "synthetic" practice session?
**A**: For each matched (PersistentID, last-played-date) pair, the
plugin inserts one `practice_sessions` row with
`duration = play_count * min(song_duration, 600)` and `started_at =
DateLAS` (`routes.py:447-452`). This backfills the journal with a
plausible total, not a true history. There is no claim of accuracy;
the user knows they are migrating.

## Q7: Why does `favorites_count` show in the preview but song_lists_count
doesn't drive any import?
**A**: Song lists are surfaced in `_extract_profile_summary`
(`routes.py:97-123`) for transparency but the importer does not write
them anywhere — Slopsmith has no first-class "song list" entity.
[NEEDS CLARIFICATION: should we materialize song lists as setlists
via the setlist plugin's API?]

## Q8: What if `_meta_db` has no row for a matched filename?
**A**: `routes.py:437-443` falls back to title="", artist="",
duration=300. The synthetic session is still created so the user's
journal totals are not silently incomplete.

## Q9: Concurrency: what if the user starts a second import while one
is running?
**A**: Each WebSocket spawns its own coroutine. There is no global
"import in progress" lock. Two simultaneous imports would interleave
batched writes and could double-write favorites (the `existing_favs`
set is captured once, not re-checked per row). Currently the UI does
not surface a second concurrent import; serial use is assumed.
[NEEDS CLARIFICATION: add a server-side mutex.]
