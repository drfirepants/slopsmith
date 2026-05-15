# Tasks — Drum Highway

Status legend: **DONE** = shipped in v3.0.0; **OPEN** = candidate work. `[P]` = parallel-safe.

## US1 — Drum highway visualization

- **DONE** 8-lane canvas renderer with DPR scaling — `screen.js` factory `init` + `draw`
- **DONE** Distinct shapes per piece (circles, diamonds, X, kick bar) — `screen.js` draw functions
- **DONE** Velocity-scaled note size — drawing path
- **DONE** Hi-hat variants (closed / pedal / open) — drawing path
- **DONE** Auto-activate via `matchesArrangement` regex — `screen.js:1769`
- **DONE** Section bands / now-line drawing — draw path
- **DONE** Per-instance Wave C refactor — `createFactory` at `screen.js:709`

## US2 — MIDI scoring

- **DONE** Web MIDI subscription, focus-routed dispatch — `screen.js` MIDI handler block
- **DONE** ±50 ms hit window — `HIT_TOLERANCE` constant
- **DONE** Hit / miss / wrong-piece feedback (lane flash, note color) — draw path
- **DONE** Streak counter + accuracy % — scoring block
- **OPEN** [P] Persist score / accuracy history per song
- **OPEN** [P] Latency calibration slider in settings

## US3 — Custom mapping

- **DONE** "Learn" mode UI per lane — settings render
- **DONE** localStorage persistence — `STORE_KEYS.customMapping = 'drums_custom_map'`
- **DONE** Validator that strips poison keys + drops invalid pairs — `screen.js:91-130`
- **DONE** Reset Map button — settings render

## US4 — Sound

- **DONE** WebAudioFont GM drum preset load — `_audioCtx` block
- **DONE** Volume slider + persistence (`drums_synth_vol`) — settings render
- **OPEN** [P] Multiple kit choices (acoustic / electronic / 808)
- **OPEN** [P] Per-lane volume trims

## US5 — Splitscreen

- **DONE** Per-instance state closured in `createFactory` — entire factory body
- **DONE** Focus-routed MIDI dispatch via `slopsmithSplitscreen.isActive()` — multiple call sites at `screen.js:613-650`
- **DONE** Outgoing-panel held-pad clear on focus change — focus-change listener
- **DONE** Per-panel inline settings docked beside its own gear icon — settings-panel render

## Cross-cutting

- **DONE** Idempotent factory exposure (no double-wrap)
- **DONE** Resize handler registered + cleaned up per instance — `_onWinResize` add/remove
- **OPEN** [P] Test harness for pure helpers (lane mapping, validator, hit-window math) — none today
- **OPEN** Document the GM-note table + custom-mapping format in CLAUDE.md (currently only README)

## Documentation

- **DONE** README with lane table, custom-mapping how-to, screenshots
- **OPEN** [P] CHANGELOG / version history
