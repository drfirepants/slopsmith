# Tasks — Fretboard View

Status legend: **DONE** = shipped in v1.0.0; **OPEN** = candidate work. `[P]` = parallel-safe.

## US1 — Live fretboard overlay

- **DONE** Toggle button injection — `screen.js:24-36`
- **DONE** Canvas creation + dismiss `✕` sibling — `screen.js:55-90`
- **DONE** Resize-aware positioning (tracks controls bar height) — `_fbResize`
- **DONE** Draw loop (strings, frets, dot markers, fret numbers) — `_fbDraw`
- **DONE** Active-note rendering with glow + fret number — `screen.js:228-267`
- **DONE** Sustain fade — `_fbGetActiveNotes` alpha calculation
- **DONE** DPR-aware canvas sizing
- **DONE** Idempotent `playSong` wrap — `screen.js:319-321`

## US2 — Dismiss

- **DONE** `✕` button removes canvas + listener — `_fbToggle` → `_fbRemoveCanvas`
- **DONE** Toggle button reflects state (text + class swap) — `_fbToggle`

## US3 — Chords

- **DONE** Chord notes lit simultaneously — `_fbGetActiveNotes` chord branch

## Cross-cutting

- **DONE** Rocksmith string-color palette (low-E red → high-e purple) — `FB_STRING_COLORS`, `FB_STRING_BRIGHT`
- **DONE** Single dots at 3/5/7/9/15/17/19/21, double at 12/24 — `FB_DOT_FRETS`, `FB_DOUBLE_DOT`
- **DONE** Reversed display order (high-e on top) — `drawString = FB_STRINGS - 1 - rsString`
- **OPEN** [P] Bass arrangement support (4 strings, hide top 2 lanes)
- **OPEN** [P] Extended-range support (7-string, 8-string)
- **OPEN** [P] Persist toggle state in localStorage
- **OPEN** [P] Display tuning name (read from `highway` if available)
- **OPEN** Test harness for `_fbGetActiveNotes` (pure helper) — none today

## Documentation

- **DONE** README with install + how-it-works
- **OPEN** [P] CHANGELOG / version history
