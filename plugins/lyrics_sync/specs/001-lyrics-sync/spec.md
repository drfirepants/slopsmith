# Feature Specification: Lyrics Sync

**Feature Branch**: `001-lyrics-sync`
**Created**: 2026-05-09 (retrospective)
**Status**: Implemented (v1.0.0); superseded by `lyrics_karaoke`
**Input**: `README.md`, `routes.py`, `screen.html`, `screen.js`.

## User Scenarios & Testing

### User Story 1 — Generate synced lyrics from a vocals stem (P1)

As a Slopsmith user with sloppak songs, I want to paste plain lyrics
text and get back per-line timestamps aligned to the song's vocals
stem, so I can either save them into the sloppak (for in-player
display) or export an `.lrc` for sharing.

**Why this priority**: Core function. The screen does nothing else.

**Independent Test**: Pick a sloppak that has a vocals stem, paste a
verse of lyrics, hit Align. The plugin POSTs to the demucs server's
`/align`, displays a preview with `[mm:ss.xx]` timestamps, and offers
"Save to song" / "Export .lrc" actions.

**Acceptance Scenarios**:

1. **Given** a sloppak with a vocals stem and a configured demucs
   server URL, **When** the user submits lyrics text, **Then** the
   plugin returns `{segments: [{start, end, text}, ...]}` from the
   server and renders them in a preview list.
2. **Given** the demucs server is not configured, **When** the user
   visits the screen, **Then** the status banner shows "No demucs
   server configured" and the Align button is disabled.
3. **Given** a PSARC song is selected, **When** the user attempts
   alignment, **Then** the backend MUST respond `400` with "No
   vocals stem found".

---

### User Story 2 — Save synced lyrics into the sloppak (P1)

As a user who's done the alignment, I want to write the result into
the sloppak so it shows up during in-player lyrics display without
having to re-align next session.

**Why this priority**: Without persistence the alignment is gone after
the user closes the page.

**Independent Test**: After alignment, click "Save to song". Verify
the sloppak's `lyrics.json` exists with `[{t, d, w}]` entries, and
that `manifest.yaml` has `lyrics: lyrics.json`.

**Acceptance Scenarios**:

1. **Given** alignment segments are present, **When** the user clicks
   Save, **Then** the backend writes
   `<source_dir>/lyrics.json` with one entry per segment
   (`t = round(start, 3)`, `d = round(end-start, 3)`, `w = text`) and
   patches `manifest.yaml` with `lyrics: lyrics.json`.
2. **Given** PyYAML is missing in the runtime, **When** Save is
   called, **Then** the manifest patch falls back to a text-append of
   `lyrics: lyrics.json` if the key isn't already present.

---

### User Story 3 — Export to a standalone `.lrc` file (P2)

As a user who wants to share synced lyrics outside Slopsmith, I want
to download an `.lrc` with optional `[ti:]` / `[ar:]` headers.

**Why this priority**: Useful but not required for in-player use.

**Independent Test**: After alignment, fill in title/artist, click
Export. The browser receives a download with name
`<artist> - <title>.lrc` (sanitised) containing one
`[mm:ss.xx]<text>` line per segment plus `[by:Slopsmith Lyrics Sync]`.

**Acceptance Scenarios**:

1. **Given** alignment segments and a title, **When** Export is
   called, **Then** the response sets
   `Content-Disposition: attachment; filename="<safe_name>.lrc"`.
2. **Given** filename-unsafe characters in title/artist (`/`, `\`),
   **When** Export is called, **Then** they are replaced with `_`.

---

### User Story 4 — Choose alignment granularity (P3)

As a user, I want to pick line / word / syllable granularity for the
alignment so I can match downstream needs (line for plain lyrics
display, syllable for karaoke).

**Why this priority**: Nice to have. The default `line` is fine for
most users.

**Independent Test**: Send the same text with different granularity
values and confirm the server returns proportionally more / fewer
segments. The plugin passes the value through unchanged.

**Acceptance Scenarios**:

1. **Given** the user picks `granularity=word`, **When** Align is
   called, **Then** the form-data POST to the server includes
   `granularity=word`.

## Functional Requirements

- **FR-001**: `GET /api/plugins/lyrics_sync/status` MUST return
  `{available: bool, server_url?, reason?}` based on a `GET
  /health` probe to the configured demucs server (5 s timeout).
- **FR-002**: `POST /api/plugins/lyrics_sync/align` MUST accept
  `{filename, lyrics_text, language?, granularity?}`, locate the
  sloppak's vocals stem via `manifest.stems[id=vocals].file`, and
  forward a multipart POST to `<server>/align` with file +
  `text` + `language` + `granularity`. 300 s timeout.
- **FR-003**: `POST /api/plugins/lyrics_sync/export` MUST return a
  `.lrc` text response with the standard `[mm:ss.xx]` header per line
  and an optional `[ti:]` / `[ar:]` block.
- **FR-004**: `POST /api/plugins/lyrics_sync/save` MUST persist
  `lyrics.json` and patch `manifest.yaml` (or `manifest.yml`)
  in the sloppak source dir.
- **FR-005**: Vocals stem location MUST be resolved via the shared
  `sloppak` module (`is_sloppak`, `resolve_source_dir`,
  `load_manifest`).
- **FR-006**: Demucs server URL MUST be read from
  `<config_dir>/config.json` under the key `demucs_server_url`. The
  same key is shared with `lyrics_karaoke` and `stems`.
- **FR-007**: The plugin MUST NOT fall back to local Whisper if the
  server is unavailable; it MUST surface the error.
- **FR-008**: The plugin MUST NOT modify zip-form sloppaks
  (`*.sloppak`). [NEEDS CLARIFICATION: current code writes
  `lyrics.json` and the manifest into `source_dir`, which is the
  unpacked cache for zip sloppaks; the zip itself is not re-zipped.
  This means the saved lyrics survive only as long as the unpack
  cache. `lyrics_karaoke` re-zips; `lyrics_sync` does not. Confirm
  intended behaviour.]

## Out of Scope

- Pitch extraction (lives in `lyrics_karaoke`).
- Editing alignment in-browser (no inline editor).
- Translating / transliterating lyrics.
- Running Whisper locally if the server is down.
