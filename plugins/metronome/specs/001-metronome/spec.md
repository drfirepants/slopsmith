# Feature Specification: Metronome Overlay

**Feature Branch**: `001-metronome`
**Created**: 2026-05-09 (retrospective)
**Status**: Implemented (v1.0.0)
**Input**: Plugin description from `README.md` and `plugin.json`.

## User Scenarios & Testing

### User Story 1 — Hear an audible click on every beat (Priority: P1)

As a player practising a song, I want a click on every beat (with an
emphasized click on each measure's downbeat) so I can lock my timing
without staring at a metronome app.

**Why this priority**: This is the plugin. Without it the rest is
decoration.

**Independent Test**: Load a song with a known tempo, click the
"Metronome" button in the player controls, hit play. Each beat in the
song's beat map produces an audible click; the click on the first beat
of every measure is higher pitched (1500 Hz vs 1000 Hz).

**Acceptance Scenarios**:

1. **Given** a song is loaded and playing, **When** the user clicks
   "Metronome ✓", **Then** a sine click is emitted within ±50 ms of
   each beat in `highway.getBeats()`.
2. **Given** the metronome is enabled, **When** a beat is flagged as a
   measure start (`beat.measure >= 0`), **Then** the click frequency is
   1500 Hz instead of 1000 Hz.
3. **Given** the user seeks past several beats, **When** playback
   resumes, **Then** the plugin does NOT play the skipped clicks (the
   50 ms gating tolerance suppresses catch-up bursts on seeks).

---

### User Story 2 — See a visual flash on the highway (Priority: P2)

As a player who plays with the volume off, I want a subtle amber pulse
on the highway on every beat so I can still feel the pulse visually.

**Why this priority**: Useful, but redundant with the click.

**Independent Test**: Mute the click (slider to 0%) and enable
"Flash". Confirm the highway gets an amber gradient flash on each beat,
brighter on downbeats, and that the flash fades within ~5 frames.

**Acceptance Scenarios**:

1. **Given** Flash is enabled, **When** a beat triggers, **Then** an
   amber gradient (alpha 0.15 normal / 0.35 measure) is drawn over the
   highway play-line band (y from 72 % to 90 % of canvas height).
2. **Given** Flash is disabled, **When** a beat triggers, **Then** no
   draw-hook output is produced even though the click still plays.

---

### User Story 3 — Persist preferences across reloads (Priority: P3)

As a returning user, I want my volume and "flash" preference remembered
across page reloads so I don't have to reconfigure each session.

**Why this priority**: Quality-of-life, not core function.

**Independent Test**: Set volume to 60 %, disable flash, reload the
page, open the player controls. The slider reads 60 %, the flash
checkbox is unchecked.

**Acceptance Scenarios**:

1. **Given** the user changes the volume slider, **When** the page is
   reloaded and any song is started, **Then** the metronome controls
   show the previously-chosen volume.
2. **Given** the user disables flash, **When** they re-enable the
   metronome later, **Then** the flash stays off until explicitly
   re-enabled.

## Functional Requirements

- **FR-001**: The plugin MUST inject a "Metronome" toggle button into
  `#player-controls`, placed adjacent to `#btn-lyrics` when present.
- **FR-002**: The plugin MUST poll the highway at 60 Hz; on each tick
  it MUST identify the most recent beat with `beat.time <= getTime()`
  via binary search.
- **FR-003**: A click MUST fire only when the elapsed time since the
  detected beat is ≤ 50 ms (avoid catch-up on seek).
- **FR-004**: Click frequency MUST be 1500 Hz on `beat.measure >= 0`,
  1000 Hz otherwise; envelope is a 60 ms exponential ramp from
  `volume` to 0.001.
- **FR-005**: Visual flash MUST register a draw hook on the highway
  with `addDrawHook(...)`. Hook MUST early-return when
  `flashAlpha < 0.005`. Alpha decays per-frame by ×0.88.
- **FR-006**: Settings persistence: `enabled`, `volume`, `flashEnabled`
  MUST live on a single `window[MET_SETTINGS_KEY]` object so re-loading
  `screen.js` reuses existing state. [NEEDS CLARIFICATION: README says
  settings are persisted, but `_metSettings` is in-memory only — there
  is currently no localStorage write. Treat this as a known gap.]
- **FR-007**: The plugin MUST NOT add nav entries, screens, settings
  pages, or backend routes. The plugin manifest exposes only `script`.
- **FR-008**: All wrappers (`playSong` monkey-patch, draw hook,
  setInterval) MUST be guarded so a re-evaluation of `screen.js` does
  not double-install them.

## Out of Scope

- Loading custom click samples.
- Tap-tempo / manual BPM override.
- Subdivisions (eighth-note clicks, polyrhythms, etc).
- Per-song persisted volume / on-state.
- Backend persistence of any kind.
