# Analysis — Lyrics Sync

## Coverage

| Spec area | Implementation | Notes |
|---|---|---|
| FR-001 (status) | `ls_status` | OK. |
| FR-002 (align) | `ls_align` | OK; 300 s timeout matches longest songs. |
| FR-003 (export) | `ls_export` | OK; LRC header optional. |
| FR-004 (save + manifest patch) | `ls_save` | OK for directory sloppaks, lossy for zip sloppaks. |
| FR-005 (sloppak module) | `_find_vocals_stem` | OK. |
| FR-006 (shared config key) | `_get_demucs_server_url` | OK; same key as `lyrics_karaoke` and `stems`. |
| FR-007 (no local fallback) | n/a | OK by omission. |
| FR-008 (zip sloppak handling) | not implemented | **DRIFT** — see Save below. |

## Drift

1. **Save does not re-zip zip-form sloppaks.** Lyrics persist in the
   unpack cache only; deleting the cache loses them. The newer
   `lyrics_karaoke` plugin re-zips. Either lift the re-zip helper
   here, or formally deprecate this plugin and route saves through
   `lyrics_karaoke`.
2. **`_format_lrc_word_level` is defined but unused.** Frontend has
   no "Enhanced LRC" option to trigger it.
3. **Frontend doesn't disable the Save / Align buttons when the
   server is offline** — relies on the user reading the status
   banner. Minor UX gap.
4. **README mentions "preview panel" without specifying the data
   shape.** Acceptable for a user doc.

## Gaps

1. No tests. Backend is straightforward enough that pytest + the
   `requests-mock` library could cover all four endpoints in
   ~150 lines.
2. No deprecation pathway communicated to users. If the long-term
   plan is to fold this into `lyrics_karaoke`, a banner on
   `screen.html` and a `lyrics_karaoke`-side redirect would help.
3. The `align` route returns the upstream server's JSON verbatim,
   including any unexpected fields. That's flexible but means a
   server-side schema change can break the frontend silently.

## Recommendations

1. **Decide migration**: either deprecate (banner + redirect to
   `lyrics_karaoke`) or fold zip-aware save back into this plugin.
   Status quo is the worst of both — duplicated code that diverges.
2. **Wire the word-level formatter** or delete it. Dead code rots.
3. **Add a tiny pytest suite** that mocks the demucs server. Catches
   regressions on serialization shapes (`lyrics.json` field names,
   LRC formatting).
4. **Pin a server contract** — at minimum, document the expected
   response shape from `/align` (e.g. as a comment block in
   `routes.py`) so server-side schema drift is detectable.
