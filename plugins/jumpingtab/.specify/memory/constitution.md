# Jumping Tab — Plugin Constitution

A Yousician-style 2D horizontal tab visualization. Notes scroll right→left along color-coded string lines; trajectory arcs connect consecutive monophonic notes; a glowing ball hops along the arcs; chord-shape diagrams scroll on a secondary canvas above the tab. Registered as a setRenderer factory (slopsmith#36).

## Core Principles

### I. Full-Replacement Renderer, Manual Selection
The plugin replaces the highway via `setRenderer` rather than overlaying it. It's arrangement-agnostic (works on any tuning / arrangement) so it does NOT declare `matchesArrangement` — Auto mode will not pick it; the user picks "Jumping Tab" from the visualization picker.

### II. Per-Instance Under Splitscreen (Wave C)
Rendering canvas, chart caches, trajectory + technique arc caches, and listener refs are closured inside `createFactory()`. N splitscreen panels can render different arrangements of the same song without cache cross-talk. Trajectory cache multiplies by N — accepted cost given high cache hit rate within a song.

### III. Pure Helpers Are Module-Scope and Tested
Geometry math, time→x mappings, trajectory builder, bezier interpolation, and range search live at module scope (not inside the factory closure) because they're stateless. `test/test.html` exercises them directly without a Slopsmith instance.

### IV. Standalone Demo Harness
`demo/index.html` loads `screen.js` with synthetic data and renders static frames so contributors can iterate / take screenshots without running Slopsmith. The demo state (`window.__jumpingtab_state` / `window.__jumpingtab_demo`) preserves the pre-Wave-C module-level mini-state so existing test bindings still work.

### V. String Count From Core, Not Assumed
`bundle.stringCount` (slopsmith core slopsmith#93) drives lane count. 4-string bass renders 4 lanes, 6-string guitar 6, extended-range 7/8-string GP imports render the full count without spillover. No hard-coded `STRINGS = 6`.

### VI. Multi-Author Visual Identity
The current visual style merges contributions from byrongamatos (setRenderer + Wave C, technique capsules, bend indicators, trajectory hopping ball, dynamic string count), alleexx (chord-box rendering, Rocksmith-aligned palette, reduced hit-line glow), topkoa (early splitscreen-pane factory, superseded), and rymarshall (WS URL fix, obsoleted by setRenderer migration). Constants like `DISABLE_RINGS = true` reflect alleexx's preference and stay opt-out style.

## Inherits from Slopsmith Core Constitution

- **Vanilla JS, no framework, no bundler.**
- **Plugin isolation**: registers via `window.slopsmithViz_jumpingtab = createFactory` (slopsmith#36 setRenderer contract).
- **Manifest-driven loading**: `plugin.json` declares `id: "jumpingtab"`, `type: "visualization"`.
- **Reads `bundle.notes` / `bundle.chords` / `bundle.stringCount`** from core's setRenderer-supplied bundle on each draw frame.
- **Single-user, single-host.**

**Version**: 3.0.0 | **Ratified**: 2026-05-09 | **Last Amended**: 2026-05-09
