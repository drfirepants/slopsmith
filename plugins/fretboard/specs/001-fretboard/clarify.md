# Clarifications — Fretboard View

## Q1: Why the legacy `playSong` wrap and not setRenderer?
**A**: The plugin is an overlay, not a replacement renderer. The setRenderer factory contract (slopsmith#36) replaces the highway; the fretboard is meant to coexist with it. Hence the older hook pattern.

## Q2: Does this work for bass arrangements (4 strings)?
**A**: `[NEEDS CLARIFICATION]` — `FB_STRINGS = 6` is hard-coded. Bass notes still arrive on the highway; they'd map to strings 0-3 of the 6-string display. Bottom 2 strings would just stay dark. Not ideal but functional.

## Q3: Does this work for 7-string / extended-range guitars?
**A**: No. Strings beyond index 5 are clipped. Worth a future fix.

## Q4: How does the plugin know the song's tuning?
**A**: It doesn't read tuning explicitly. It just shows the fret position relative to standard 6-string layout. Note shapes are correct for any tuning since the highway already supplies the (string, fret) pairs that the user must finger.

## Q5: Why ±80 ms for active-note window?
**A**: Larger than the drums plugin's 50 ms hit window — the fretboard is illustrative not scoring, so it errs toward "show the note slightly early and slightly after" for clarity.

## Q6: What's the relationship to the guitar-theory plugin's fretboard?
**A**: Independent. Guitar Theory Lab is a full-screen learning tool with quizzes/jam mode; this plugin is a passive overlay during playback. No code shared.

## Q7: Why is the dismiss `✕` a sibling of the canvas, not drawn on it?
**A**: `pointer-events: none` on the canvas (so clicks fall through to the highway behind it). The dismiss button needs `pointer-events: auto`; making it a separate sibling is cleaner than re-enabling pointer-events on a sub-region of the canvas.

## Q8: How does the toggle persist across songs?
**A**: `_fbEnabled` is module-scope. Switching songs re-injects the button; if `_fbEnabled` was true the canvas is re-created. Persistence does NOT extend across browser reloads — `_fbEnabled` resets to `false`. `[OPEN]` whether to add localStorage persistence.
