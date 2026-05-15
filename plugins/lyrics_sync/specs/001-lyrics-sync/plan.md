# Implementation Plan — Lyrics Sync

Single-screen plugin with four backend endpoints. Thin wrapper over the
Slopsmith Demucs Server's `/align`.

## Files

- `plugin.json` — id `lyrics_sync`, declares screen + script + routes.
- `routes.py` (272 lines) — backend endpoints.
- `screen.html` — wizard UI.
- `screen.js` — UI logic, server polling, preview renderer.
- `README.md` — user docs.

## Backend (`routes.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/plugins/lyrics_sync/status` | GET | Probe `<demucs>/health`, return availability + URL. |
| `/api/plugins/lyrics_sync/align` | POST | Resolve sloppak vocals stem, forward multipart POST to `<demucs>/align`, return server JSON. |
| `/api/plugins/lyrics_sync/export` | POST | Format alignment segments as `.lrc`, set `Content-Disposition`. |
| `/api/plugins/lyrics_sync/save` | POST | Write `lyrics.json` into source dir, patch `manifest.yaml` with `lyrics: lyrics.json`. |

### Helpers

- `_get_demucs_server_url()` — reads `<config_dir>/config.json`,
  returns `demucs_server_url` (rstripped of trailing `/`).
- `_find_vocals_stem(filename)` — uses `sloppak.is_sloppak` +
  `sloppak.resolve_source_dir` + `sloppak.load_manifest`. Returns
  `None` for PSARC.
- `_format_lrc(segments)` — `[mm:ss.xx]<text>` per line.
- `_format_lrc_word_level(segments)` — Enhanced LRC with inline
  `<mm:ss.xx>` per word. (Defined but not currently called by any
  route — leftover from word-level export experiments.)

### Setup contract

```python
def setup(app, context):
    _config_dir = context["config_dir"]
    _get_dlc_dir = context["get_dlc_dir"]
    SLOPPAK_CACHE_DIR = os.environ["STATIC_DIR"] / "sloppak_cache"
```

## Frontend

`screen.html` is a wizard:

1. Status banner (alignment server availability)
2. Song picker (search + click)
3. Lyrics text area with optional file upload
4. Granularity selector (line / word / syllable)
5. Language hint
6. Align button → preview pane → Save / Export actions

## Integration with Slopsmith Core

- **Config sharing**: reads `demucs_server_url` from the same
  `config.json` used by `stems` and `lyrics_karaoke`.
- **Sloppak module**: depends on `sloppak.is_sloppak`,
  `resolve_source_dir`, `load_manifest`.
- **Library API**: frontend uses `/api/library?q=...` for song search.
- **Static dir**: `STATIC_DIR/sloppak_cache` for unpack cache (env
  var, defaults to `/app/static`).

## Out of Scope / Deferred

- Re-zipping zip-form sloppaks after Save (see clarify.md Q2).
- Running Whisper locally.
- Inline alignment editing.
- Backend tests (no test harness in repo).
