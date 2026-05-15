# Implementation Plan — Base Game Song Extractor

## Architecture

**Frontend** (`screen.html` 17 lines, `screen.js` 135 lines):
- DOM-based plain HTML — no canvas, no framework.
- Three sections: `#disc-status`, `#disc-songs` (or `#disc-progress` / `#disc-result`).
- Single hooked `showScreen` wrapper (idempotent via `__slopsmithDiscExtractHooksInstalled`).
- WebSocket client connects to `/ws/plugins/disc_extract/extract` and updates `#disc-bar` width + `#disc-stage` text per frame.

**Backend** (`routes.py` 326 lines, `disc_extractor.py` 467 lines):
- `setup(app, context)` captures `get_dlc_dir`, `extract_meta`, `meta_db` from core context.
- HTTP `GET /api/plugins/disc_extract/status` returns the catalogue + extracted-flags.
- WebSocket `/ws/plugins/disc_extract/extract` runs `disc_extractor.extract_all` with a progress callback that pushes JSON frames.
- `_find_rs_dir(dlc_dir)` resolves the Rocksmith install location.
- `psarc.read_psarc_entries` reads the source `songs.psarc`; the extractor builds per-song aggregate graph + HSAN and writes new PSARCs.

## Integration Points (Slopsmith core)

| Surface | How used |
|---|---|
| `context['get_dlc_dir']` | locate output dir; verify DLC config |
| `context['extract_meta']` | post-extraction metadata cache |
| `context['meta_db']` | library DB write so songs appear without restart |
| `psarc` (top-level helper module) | reading the source `songs.psarc` |
| `window.showScreen` | hook to lazy-load status when the screen is opened |
| `plugin.json:nav.screen = "disc-extract"` | core mounts the screen at `plugin-disc_extract` (fragments stripped) |

## File Map

| Path | Purpose | Lines |
|---|---|---|
| `plugin.json` | manifest (id, nav, scripts, routes) | ~10 |
| `screen.html` | minimal layout: status + songs + progress + result | 17 |
| `screen.js` | status fetch + WebSocket extraction client | 135 |
| `routes.py` | FastAPI status endpoint + WS extract endpoint + RS-dir discovery | 326 |
| `disc_extractor.py` | PSARC unpack + per-song repack engine | 467 |
| `README.md` | install + Docker mount instructions | ~50 |

## Tech Stack

- Python: FastAPI, asyncio, pathlib, internal `psarc` helper.
- JS: vanilla, Tailwind classes, WebSocket API, `fetch`.
- Docker: read-only `/rocksmith` mount alongside the existing Slopsmith DLC mount.

## Out-of-Plan / Won't Build

- DLC pack splitting (only base game `songs.psarc`).
- Cross-platform PSARC variants (`_m.psarc`).
- Re-extraction / overwrite UX — skip is the contract.
- Background/queued extraction outside the request lifecycle.
