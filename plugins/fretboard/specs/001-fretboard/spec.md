# Feature Specification: Fretboard View

**Plugin id**: `fretboard`
**Status**: Shipped (v1.0.0)
**Type**: Player-overlay visualization (legacy `playSong` hook)

## Summary

A horizontal 6-string × 24-fret diagram drawn as an overlay below the highway. Active notes light up on the fretboard as they arrive, with Rocksmith string colors and a glow halo. Toggleable via a "Fretboard" button in player controls.

## User Stories

### US1 — See finger positions on a fretboard (Priority: P1)

**Given** I'm playing a song on the highway,
**When** I click the "Fretboard" button in player controls,
**Then** a horizontal fretboard appears below the highway, the active notes light up with their string color and fret number, and they fade through their sustain duration.

### US2 — Dismiss the overlay (Priority: P2)

**Given** the fretboard overlay is showing,
**When** I click the `✕` at the top-right of the overlay (or click "Fretboard" again),
**Then** the canvas + dismiss button are removed and the toggle reverts to off.

### US3 — See chords (Priority: P2)

**Given** a chord plays,
**When** the chord's time reaches the now-window,
**Then** every note in the chord lights up simultaneously (not sequentially).

## Functional Requirements

- **FR1**: Toggle button MUST be injected into `#player-controls` once per song open (idempotent on re-injection).
- **FR2**: Overlay canvas MUST be `pointer-events: none`; dismiss `✕` MUST be `pointer-events: auto`.
- **FR3**: Canvas position MUST track the player controls bar height (recomputed on every `resize`).
- **FR4**: 6 strings × 24 frets layout, with single dot markers at frets 3/5/7/9/15/17/19/21 and double dots at 12 and 24.
- **FR5**: Active-note window: ±80 ms around current time; sustain notes fade from alpha 1 → 0.3 over the sustain length.
- **FR6**: String colors MUST match Rocksmith convention (`FB_STRING_COLORS` for inactive, `FB_STRING_BRIGHT` for active).
- **FR7**: `screen.js` MUST be idempotent against re-eval — `playSong` wrap installed exactly once via `__slopsmithFretboardHooksInstalled`.
- **FR8**: Plugin MUST NOT mutate highway state.

## Non-Functional Requirements

- DPR-aware sizing.
- 60 fps target; per-frame work is small (24 frets × 6 strings + active-note loop).
- Notes array is sorted by time — active-note search breaks once `n.t > t + 0.5` (early exit).

## Out of Scope

- Microphone / scoring (read-only display).
- Editing notes / changing tuning.
- Splitscreen support (legacy single-instance overlay).
- Bass / 7-string display (hard-coded 6 strings).
