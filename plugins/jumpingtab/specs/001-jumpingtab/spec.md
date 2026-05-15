# Feature Specification: Jumping Tab

**Plugin id**: `jumpingtab`
**Status**: Shipped (v3.0.0, Wave C)
**Type**: Visualization renderer (full replacement via setRenderer factory)

## Summary

Replaces Slopsmith's default highway with a 2D horizontal tab view: notes scroll right→left along color-coded string lines, a glowing ball hops along parabolic arcs that connect consecutive monophonic notes, technique capsules render hammer-ons / pull-offs / slides / bends, and a secondary canvas above the tab scrolls active and upcoming chord-shape diagrams.

## User Stories

### US1 — Watch a song as a horizontal hopping-ball tab (Priority: P1)

**Given** I open a song,
**When** I select "Jumping Tab" from the player's visualization picker,
**Then** the highway is replaced with a horizontal tab where notes scroll right→left toward a hit line, color-coded by string in Rocksmith convention (string 0 = pink, 1 = yellow, 2 = cyan, etc.), with a hopping ball tracing the melody and squashing on impact at the hit line.

### US2 — See chord shapes in advance (Priority: P2)

**Given** the song contains chords,
**When** chord regions arrive,
**Then** the active chord shape renders on a secondary canvas above the tab (open / muted / fingered strings, fret numbers, finger numbers, position label), and upcoming distinct chord shapes scroll toward the hit line. Consecutive identical chords are deduped (held shape doesn't draw N times).

### US3 — Read techniques (Priority: P2)

**Given** the arrangement contains hammer-ons / pull-offs / slides / bends,
**When** those notes render,
**Then** hammer-ons / pull-offs / slides appear as fused capsules with labelled arcs above; bends get amber arrows with conventional labels (`½`, `full`, `1½`, `2`).

### US4 — Use under splitscreen (Priority: P2)

**Given** splitscreen with N panels,
**When** each panel selects "Jumping Tab",
**Then** each panel has its own canvas, chart cache, trajectory cache, and visual state — no cross-talk.

### US5 — Adapt to extended-range guitars (Priority: P3)

**Given** an arrangement with stringCount ≠ 6,
**When** the renderer initialises,
**Then** the lane count matches `bundle.stringCount` (4 for bass, 7/8 for extended-range GP imports) without spillover.

### US6 — Density-aware sizing (Priority: P3)

**Given** a fast passage (e.g. 120 BPM 16th notes),
**When** the renderer draws,
**Then** per-note radius clamps to half the same-string neighbour gap, with a visual gutter so adjacent fret circles stay distinct.

## Functional Requirements

- **FR1**: Factory MUST be exposed at `window.slopsmithViz_jumpingtab` (slopsmith#36 contract).
- **FR2**: Factory MUST NOT declare `matchesArrangement` — manual selection only.
- **FR3**: Per-instance Wave C state (canvas, caches, listeners) MUST be closured inside `createFactory()`.
- **FR4**: Pure helpers (geometry, time→x, trajectory builder, bezier, range search) MUST stay at module scope and be testable directly.
- **FR5**: `bundle.stringCount` MUST drive lane count (no `STRINGS = 6` hard-code).
- **FR6**: Visual lookahead window: 5.5 seconds (`AHEAD = 5.5`); 1.2 seconds behind (`BEHIND = 1.2`).
- **FR7**: Hit-line at `HIT_LINE_FRAC = 0.18` of canvas width.
- **FR8**: Notes fade over `FADE_SECONDS = 1.0` after passing the hit line.
- **FR9**: Squash-on-impact window: 60 ms (`SQUASH_WINDOW_MS = 60`); impact animation duration 0.45 s.
- **FR10**: `DISABLE_RINGS = true` opts out of expanding hit-line ring animation (alleexx's preference; ring code still runs but returns early).
- **FR11**: Demo harness state (`window.__jumpingtab_state`, `window.__jumpingtab_demo`) MUST stay backward-compatible so existing `test.html` and `demo/index.html` keep working.
- **FR12**: Arrangement switching (Lead / Rhythm / Bass) MUST rebuild trajectory + chord caches in place without dispose/init churn.

## Non-Functional Requirements

- DPR-aware canvas sizing.
- 60 fps target.
- Trajectory cache multiplies by N under splitscreen (accepted cost).
- No microphone input, no scoring (out of scope).

## Out of Scope

- Microphone-based scoring.
- Settings panel for speed / colors / visibility window.
- Standalone full-screen mode (player overlay only).
- Splitscreen-pane factory contract (superseded by Wave C per-panel viz picker).
- WebSocket ownership (moved to slopsmith core in setRenderer migration; rymarshall's old fix obsolete).
