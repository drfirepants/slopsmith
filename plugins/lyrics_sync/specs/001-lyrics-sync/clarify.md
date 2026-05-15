# Clarifications — Lyrics Sync

## Q1. Why is this plugin separate from `lyrics_karaoke`?

**A.** Historical: `lyrics_sync` shipped first, providing alignment
only. `lyrics_karaoke` added pitch extraction and a karaoke ribbon, and
absorbed the alignment endpoints. `lyrics_sync` is kept around so
existing setups (and bookmarks pointing at the old screen) keep
working. New work should go into `lyrics_karaoke`.

## Q2. Does saving lyrics survive a re-unpack of a zip sloppak?

**A.** No. `routes.py:ls_save` writes `lyrics.json` and patches
`manifest.yaml` inside the *unpack cache* directory (resolved via
`sloppak_mod.resolve_source_dir`). For a directory-form sloppak this
is the canonical location and is durable. For a zip-form `.sloppak`,
the save lands in the unpack cache and is lost when the cache is
cleared. `lyrics_karaoke` solved this by adding a re-zip pass; this
plugin did not. Treat as a known limitation.

## Q3. Why is `granularity` exposed but not heavily documented?

**A.** The README mentions it briefly. The server's `/align` endpoint
supports line / word / syllable, but the saved `lyrics.json` shape
treats every segment as one entry regardless. So saving a
syllable-granularity result yields one entry per syllable (with the
syllable as `w`); saving a line-granularity result yields one entry
per line. The chosen value is mostly meaningful for `.lrc` exports.

## Q4. Why no fallback when the demucs server is offline?

**A.** Whisper is too heavy to bundle in the Slopsmith Docker image —
it would require torch + CUDA + a ~140 MB model. The split keeps
Slopsmith's image small and the demucs server optional. Users who
don't run the server simply don't get this plugin's screen.

## Q5. What's the difference between the `/align` endpoint here and
the one in `lyrics_karaoke`?

**A.** None at the wire level. Both POST to `<demucs>/align` with the
same form-data shape. `lyrics_karaoke` adds a per-syllable pitch step
afterwards.

## Q6. Why does `_format_lrc` read `seg["start"]` directly with no
defensive parsing?

**A.** This plugin's `align` route returns the upstream server's
response verbatim (`return resp.json()`); the server is trusted to
emit well-formed segments. `lyrics_karaoke` has more defensive
parsing because its segments cross more boundaries (preview, save,
pitch).
