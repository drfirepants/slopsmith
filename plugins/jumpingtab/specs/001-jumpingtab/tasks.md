# Tasks — Jumping Tab

Status legend: **DONE** = shipped in v3.0.0; **OPEN** = candidate work. `[P]` = parallel-safe.

## US1 — Hopping-ball tab visualization

- **DONE** Right-to-left scrolling notes — draw chain
- **DONE** Color-coded string lines (Rocksmith palette) — palette section
- **DONE** Trajectory arcs (dashed cyan) connecting consecutive monophonic notes — trajectory builder
- **DONE** Hopping ball with squash on hit-line crossing — ball draw
- **DONE** Beat / measure ticks under notes
- **DONE** Section bands with badge in header
- **DONE** Progress bar with mm:ss timestamps along bottom
- **DONE** setRenderer registration — `screen.js:1711` `window.slopsmithViz_jumpingtab = createFactory`

## US2 — Chord-box rendering

- **DONE** Secondary canvas above tab with active chord shape — chord-box block
- **DONE** Open / muted / fingered strings, fret + finger numbers, position label
- **DONE** Upcoming distinct chord shapes scrolling toward hit line
- **DONE** Consecutive identical chord dedup — held shape doesn't redraw N times
- **DONE** Chord-template lookup via `bundle.chords[i].template` (slopsmith#92)

## US3 — Techniques

- **DONE** Hammer-on / pull-off / slide as fused capsules with labelled arcs — technique-arc draw
- **DONE** Bend amber arrows with labels (`½`, `full`, `1½`, `2`)

## US4 — Splitscreen

- **DONE** Per-instance state closured in `createFactory()` — Wave C refactor
- **DONE** Per-panel chord-box rendering, trajectory caches, visual state — independent
- **DONE** Edge-detected `bundle.isReady` per-instance — `screen.js:1664`

## US5 — Dynamic string count

- **DONE** `bundle.stringCount` drives lane count (slopsmith#93) — `screen.js:1628-1630`
- **DONE** No hard-coded `STRINGS = 6`

## US6 — Density-aware sizing

- **DONE** Per-note radius clamps to half same-string neighbour gap — sizing block
- **DONE** Visual gutter between adjacent fret circles

## Cross-cutting

- **DONE** Pure helpers at module scope (geometry, time→x, trajectory, bezier, range search)
- **DONE** `test/test.html` exercises pure helpers
- **DONE** `demo/index.html` standalone renderer with synthetic data and `?scene=` query
- **DONE** Headless Chrome screenshot recipe in README
- **DONE** Backward-compat demo state (`window.__jumpingtab_state`, `window.__jumpingtab_demo`)
- **DONE** Multi-author attribution in README
- **OPEN** [P] Settings panel (speed / colors / visibility window) — README explicitly calls out as not built yet
- **OPEN** [P] Microphone input or scoring — README calls out as not built
- **OPEN** [P] Auto-activation (`matchesArrangement`) — deliberate omission, but a power-user might want a flag to enable it
- **OPEN** [P] CI hook for `test/test.html` (currently manual, browser-open)

## Documentation

- **DONE** Comprehensive README with screenshots, attributions, demo + test recipes
- **DONE** Demo harness pre-baked for screenshot regeneration
- **OPEN** [P] CHANGELOG / version history
- **OPEN** [P] CLAUDE.md → point at `specs/001-jumpingtab/plan.md`
