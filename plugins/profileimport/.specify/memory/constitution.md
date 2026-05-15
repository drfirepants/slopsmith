# Profile Import Plugin Constitution

The Profile Import plugin (id: `profileimport`) decrypts a Rocksmith 2014
EVAS profile file and imports its favorites, play counts, mastery, and
Score Attack data into Slopsmith. It also seeds the Practice Journal
plugin's database with synthetic sessions reconstructed from play history.

## Core Principles

### I. Decryption Stays Local
Profile bytes are never sent to a third party. Decryption uses
`PROFILE_KEY` (`routes.py:15-20`) and runs entirely in-process. The
decrypted profile is held in memory under `_stashed_profiles` keyed by
`profile_id` for the lifetime of the import flow only.

### II. Three-Step Flow: Upload → Map → Import
The user MUST upload the profile (preview), build/refresh the SongKey
mapping cache (scan PSARCs once), and finally start the import. The
import button is disabled until both `_piProfileId` is set and
`mapping-status.cached_mappings > 0` (`screen.js:116-124`).

### III. WebSocket for Long-Running Work
Both the PSARC scan (`/ws/.../build-mapping`) and the import
(`/ws/.../import`) stream incremental progress. REST endpoints are
reserved for short, synchronous operations (status, history,
play-stats summary).

### IV. Idempotent + Forward-Compatible
Re-uploading the same profile or re-running the import overwrites
prior rows (`INSERT OR REPLACE` on `play_stats`, `score_attack`,
`songkey_map`). Existing favorites are not duplicated
(`routes.py:340-353`).

### V. Coupled to `practice_journal.db`, Not to its Plugin
Synthetic sessions are written by direct `sqlite3.connect` to
`${config_dir}/practice_journal.db` (`routes.py:387-405`). The schema
must mirror practice_journal's exactly. Constitution §V of
practice_journal binds us.

### VI. Idempotent Frontend Hooks
`__slopsmithProfileImportHooksInstalled` (`screen.js:11-13`) prevents
re-wrap of `showScreen`. Drop-zone init checks `_piInitialized`
(`screen.js:32`).

## Inheritance from Slopsmith Core

Uses `context["config_dir"]`, `context["meta_db"]`, and
`context["get_dlc_dir"]`. Imports `psarc.read_psarc_entries` from the
host's `lib/`. The mapping scan reads every `*.psarc` in the DLC dir.
Library favorites are toggled via `_meta_db.toggle_favorite(filename)`.

## Governance

`PROFILE_KEY` is fixed by Rocksmith and never changes. Schema changes
require coordinating with practice_journal. New endpoints follow the
`/api/plugins/profileimport/...` and `/ws/plugins/profileimport/...`
prefixes.

**Version**: 1.0.0 | **Ratified**: 2026-05-09 | **Last Amended**: 2026-05-09
