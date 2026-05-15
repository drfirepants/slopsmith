# Base Game Song Extractor — Plugin Constitution

This plugin lives in the Slopsmith plugin ecosystem. Its identity is "give Rocksmith 2014 owners access to the ~56 on-disc songs from `songs.psarc` as if they were CDLC."

## Core Principles

### I. One-Shot Server Tool, Not a Player Surface
The plugin is a single screen with a Status → Extract → Done flow. It owns no playback, no highway, no library widgets. It writes PSARCs into the configured DLC directory and trusts Slopsmith core to discover them via the normal indexing path. No persistent background state; nothing to clean up between sessions.

### II. Read-Only Source, Idempotent Output
`songs.psarc` is mounted read-only at `/rocksmith` and MUST never be mutated. Extracted PSARCs are written to the DLC dir under deterministic names (`{Title} - {Artist}_p.psarc`). Re-running extraction MUST skip songs that already exist on disk — no overwrite, no churn, no duplicate copies. The "Extract Remaining" UX is the contract.

### III. Real-Time Progress over WebSocket
Long-running extraction MUST stream stage + percent via the plugin's WebSocket route, never synchronous HTTP. Disconnects show a connection-lost message; they do NOT silently abandon work — the server-side extraction continues, and re-loading the screen reflects the on-disk state.

### IV. Tolerant Path Discovery
The Rocksmith install dir is found in this order: Docker mount at `/rocksmith`, sibling of the configured DLC dir (`.../Rocksmith2014/dlc` → `.../Rocksmith2014`), then a small list of common Steam install paths. Missing `songs.psarc` is reported as a friendly "not found" state, not an error.

### V. Library Integration via Core Hook
After each successful extraction, the plugin calls Slopsmith core's `extract_meta` + `meta_db` (received via `setup(app, context)`) so the new PSARC appears in the library without restart. Core API surface is the only integration; no direct DB writes outside the provided hooks.

## Inherits from Slopsmith Core Constitution

This plugin inherits Slopsmith core's plugin-isolation principles:

- **Vanilla JS + Tailwind only** on the frontend; no bundler, no framework deps.
- **Single-user, single-host** model — no multi-tenant, no auth.
- **Plugin isolation via `load_sibling`-style context injection** — the plugin receives `get_dlc_dir`, `extract_meta`, `meta_db` through `context`, never imports core modules directly.
- **Manifest-driven loading** via `plugin.json` (id, name, nav, screen, script, routes). The plugin id `disc_extract` MUST match the directory name.
- **Idempotent script init** — `screen.js` guards against re-evaluation via `window.__slopsmithDiscExtractHooksInstalled`.

**Version**: 1.0.0 | **Ratified**: 2026-05-09 | **Last Amended**: 2026-05-09
