# Tasks — Lyrics Sync

## US1 — Generate synced lyrics (P1)

- [DONE] T101 `GET /status` health probe.
- [DONE] T102 `POST /align` — vocals stem resolution + multipart
  forward to demucs server.
- [DONE] T103 Granularity / language passthrough.
- [DONE] T104 Frontend wizard (`screen.html` + `screen.js`).
- [DONE] T105 Preview pane renders `[mm:ss.xx]` lines.

## US2 — Save into sloppak (P1)

- [DONE] T201 `POST /save` writes `lyrics.json`.
- [DONE] T202 PyYAML manifest patch with text-append fallback.
- [OPEN] T203 [P] Re-zip zip-form sloppaks after save (see
  clarify.md Q2). `lyrics_karaoke` has a `_rezip_sloppak` helper
  that could be lifted into a shared module.

## US3 — `.lrc` export (P2)

- [DONE] T301 `POST /export` produces standard LRC.
- [DONE] T302 Filename sanitisation.
- [OPEN] T303 [P] Wire `_format_lrc_word_level` to the export route
  when `granularity=word`. Currently defined but unreachable.

## US4 — Granularity (P3)

- [DONE] T401 Granularity radio buttons in `screen.html`.
- [DONE] T402 Pass-through to server.

## Cross-cutting

- [DONE] T501 Shared `demucs_server_url` config key.
- [DONE] T502 Plugin uses `setup(app, context)` contract.
- [OPEN] T503 [P] Tests — no test harness in repo. Possible
  pytest-based suite for the four endpoints (mock requests to the
  demucs server).
- [OPEN] T504 [P] Add a "this plugin is superseded — see
  Lyrics Karaoke" deprecation banner to `screen.html`.

## Migration

- [OPEN] T601 Plan to fold this plugin's screen + endpoints fully
  into `lyrics_karaoke` and ship a redirect-only stub here. Tracked
  in `slopsmith-plugin-lyrics-karaoke/screen.js` (header comment
  notes the merge already consumed the alignment endpoints in spirit;
  the screen redirect is still a TODO).
