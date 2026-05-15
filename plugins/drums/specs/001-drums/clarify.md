# Clarifications — Drum Highway

## Q1: How is "focused panel" defined under splitscreen?
**A**: `window.slopsmithSplitscreen.isActive(instanceId)` returns true for the most-recently-clicked panel. Absence of the helper OR `isActive() === false` means single-instance fast path (main player).

## Q2: Why is `_cfg.learnLane` module-scope when everything else is per-instance?
**A**: Intentional — clicking "Learn" in any panel reflects user intent globally. The next pad hit on the focused device is assigned, and the lane-row UI updates everywhere via class selector. (Per the comment block at `screen.js:5-30`.)

## Q3: What happens if a user's localStorage `drums_custom_map` is corrupt?
**A**: The validator drops invalid entries silently and falls back to standard GM mapping. Prototype-poison keys (`__proto__`, `constructor`, `prototype`) are stripped. Non-(0-127, known-lane-id) entries are dropped. Per `screen.js:91-110`.

## Q4: Can the plugin be used without a MIDI device?
**A**: Yes — it's a passive viewer when no device is selected. README confirms.

## Q5: Does the plugin work on Firefox?
**A**: Viewing yes, MIDI no. Firefox doesn't support Web MIDI API.

## Q6: How does the plugin know how many lanes to render for non-standard kits?
**A**: 8 lanes are hard-coded (`DRUM_LANES`). The note-to-lane mapping uses the GM table + custom remap. Extended kits (e.g. cowbell, splash) currently funnel into the closest lane via the editor's import-time choice. `[OPEN]` whether to add a "more lanes" mode.

## Q7: Does scoring persist across sessions?
**A**: `[NEEDS CLARIFICATION]` — searching settings persistence shows volume / device / channel persisted, but not score history. Default behaviour is per-session-only.

## Q8: What's the relationship to the editor plugin?
**A**: The editor is the authoring side. It writes drum tracks into the arrangement using `midi = string*24 + fret`. The drums plugin reads them back via the highway renderer's `bundle.notes` (slopsmith core gives the renderer factory the bundle on each draw).
