# Feature Specification: Drum Highway

**Plugin id**: `drums`
**Status**: Shipped (v3.0.0, Wave C)
**Type**: Visualization renderer (overlay canvas via setRenderer factory)

## Summary

Replaces Slopsmith's default highway with an 8-lane scrolling drum view (Hi-Hat, Snare, Tom 1-3, Crash, Ride, Kick) for Drums/Percussion arrangements. Notes scroll right→left toward a now-line. Optional MIDI drum-pad input drives accuracy scoring and triggers an embedded WebAudioFont GM drum kit. Inline settings panel docked next to the panel's gear icon.

## User Stories

### US1 — Watch a drum track on the highway (Priority: P1)

**Given** I open a song with a Drums/Percussion arrangement,
**When** I press play,
**Then** I see 8 horizontal lanes, notes scrolling right→left, distinct shapes per piece (X for hi-hat, circles for snare/toms, diamonds for crash/ride, full-width bar for kick), velocity-scaled sizing, and the auto-activated "Drums" picker.

### US2 — Practice with a MIDI drum pad (Priority: P2)

**Given** I have a MIDI drum pad connected and Chrome/Edge,
**When** I select my device in the inline settings,
**Then** hits route to the focused panel: correct hits within ±50 ms light the lane green, wrong pieces flash red, missed notes turn gray after the now-line, and a streak counter tracks consecutive hits.

### US3 — Custom-map an off-spec drum pad (Priority: P2)

**Given** my pad sends non-GM MIDI notes,
**When** I open settings → MIDI Mapping → click "Learn" next to a lane and hit a pad,
**Then** that MIDI note is bound to the lane, persisted in localStorage as `drums_custom_map`, and visible in the lane row across all splitscreen panels.

### US4 — Hear what I'm playing (Priority: P3)

**Given** the synth volume slider is non-zero,
**When** I hit a pad,
**Then** the embedded WebAudioFont GM drum kit plays the sample at the corresponding GM note (kick → 36, snare → 38, etc.).

### US5 — Use multiple drum panels in splitscreen (Priority: P3)

**Given** splitscreen with N panels each picking Drums,
**When** I click into one panel,
**Then** that panel becomes MIDI-focused; previous panel's held-pad state is cleared; only the focused panel scores.

## Functional Requirements

- **FR1**: Factory MUST be exposed at `window.slopsmithViz_drums` (slopsmith#36 contract).
- **FR2**: `createFactory.matchesArrangement(songInfo)` MUST match `/\b(?:drums|percussion|drum\s*kit)\b/i` against the arrangement name.
- **FR3**: Note-encoding convention is `midi = string * 24 + fret`. The plugin maps incoming notes to lanes via this convention (per editor plugin's drum-import path).
- **FR4**: Hit-window MUST be ±50 ms (`HIT_TOLERANCE = 0.05`).
- **FR5**: `localStorage` reads MUST tolerate `SecurityError` (returning null fallthrough).
- **FR6**: `customMapping` validator MUST strip prototype-poisoning keys and reject non-numeric / out-of-range MIDI values.
- **FR7**: Per-instance teardown MUST remove its own `resize` listener and detach from `slopsmithSplitscreen`.
- **FR8**: Kick lane MUST render as a full-width bar (not a circle) — like guitar open-string notes.

## Non-Functional Requirements

- DPR-aware canvas sizing (`window.devicePixelRatio`).
- 60 fps target; per-frame work bounded by `VISIBLE_SECONDS = 3.0` lookahead.
- Cross-instance MIDI focus change MUST be sub-frame so lane flashes don't carry over.

## Out of Scope

- Recording / authoring drums (that's the editor plugin).
- Non-MIDI hit detection (no microphone / e-drum trigger acoustic input).
- Latency calibration UI.
