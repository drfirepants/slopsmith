# Lyrics Sync Plugin Constitution

This plugin generates time-synced lyrics for sloppak songs using a
Whisper-based forced-alignment server. It is the predecessor of, and
now superseded in scope by, `lyrics_karaoke`. These principles describe
its own constrained role.

## Principles

### 1. Sloppak Only

Forced alignment requires an isolated vocals stem. PSARC songs do not
ship one, so this plugin operates exclusively on sloppak files with
`stems[id=vocals]` declared in `manifest.yaml`. PSARC songs MUST be
rejected with a clear error rather than be aligned against a full mix.

### 2. Server-Backed, Optional

The plugin is a thin client over the Slopsmith Demucs Server's
`/align` endpoint. If the server is not reachable, the plugin SHOULD
surface a clear "Cannot connect to alignment server" error and degrade
to read-only mode rather than fall back to local Whisper. Local
Whisper would balloon the plugin's footprint and break Slopsmith's
small-image promise.

### 3. Two Output Targets, One Pipeline

The same alignment result feeds both the `.lrc` export and the
in-sloppak `lyrics.json`. The export path MUST NOT diverge from the
save path: any improvement in alignment normalisation must benefit
both.

### 4. No Pitch, No Karaoke

This plugin produces *timestamps only*. It does not extract pitch and
does not draw a karaoke ribbon. That is `lyrics_karaoke`'s job.
Splitting these concerns lets users with an alignment server but no
desire for the karaoke feature still benefit, and keeps the dependency
surface minimal.

### 5. Sloppak Manifest Is the Source of Truth

The plugin writes `lyrics.json` and patches `manifest.yaml`'s `lyrics`
key. It does not maintain its own per-song database; the sloppak is
self-contained and must remain so.

## Inherits from Slopsmith Core Constitution

- Plugins MUST set up routes via `setup(app, context)` and use the
  `context["config_dir"]` and `context["get_dlc_dir"]()` helpers
  rather than reading environment variables directly.
- Plugins MUST use the shared `sloppak` module for file detection and
  source-dir resolution.
- Plugin routes live under `/api/plugins/<plugin_id>/...`.
- The plugin loader serves only the file referenced by
  `plugin.json.script`.

Where this plugin's principles disagree with the core constitution,
the core wins.
