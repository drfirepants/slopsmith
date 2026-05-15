# Clarifications — Jumping Tab

## Q1: Why no `matchesArrangement`?
**A**: The plugin is arrangement-agnostic — it works on any tuning / arrangement (Lead, Rhythm, Bass, even GP-imported extended-range). Auto mode would otherwise pick it for everything; making selection manual respects the user's intent. README spells this out explicitly.

## Q2: Why is the lookahead 5.5 s and not 8.0?
**A**: Constant comment at `screen.js:35-38`: 5.5 s matches renanboni's fork (preferred over byrongamatos's earlier 8.0 — shorter window means larger note rendering, easier to read at speed). It's a deliberate visual-design choice.

## Q3: Why do hit-line rings exist in code but get disabled?
**A**: alleexx (renanboni fork) found the expanding ring animation visually busy in dense passages. The flag `DISABLE_RINGS = true` (`screen.js:48`) opts out at draw time — `drawImpacts` still runs but returns early. Easy to flip back on for a different visual feel.

## Q4: How does the chord-box dedup work?
**A**: Distinguishes consecutive identical chords so a held shape doesn't redraw N times. Implementation is in the chord-box rendering block; uses chord-template lookup table indexed via `slopsmith#92`.

## Q5: What's the relationship to the renanboni fork?
**A**: This plugin merges several upstream forks (byrongamatos's main + alleexx's chord-box and palette work + topkoa's early splitscreen + rymarshall's WS fix). Wave C superseded topkoa's pane factory and rymarshall's WS fix; their contributions live on as architectural lineage notes in README.

## Q6: How does it handle 7- / 8-string arrangements?
**A**: `bundle.stringCount` (slopsmith#93) drives lane count. The plugin does NOT hard-code 6. Validated for 4-string bass and 7/8-string GP imports per README.

## Q7: Does demo mode require a network?
**A**: No. `demo/index.html` loads `screen.js` with synthetic data, runs in `file://` mode, and renders static frames. Used to generate the README screenshots via headless Chrome.

## Q8: Are tests automated in CI?
**A**: `[OPEN]` — `test/test.html` is browser-only ("Open the file directly"). No CI pipeline reference in the README. Manual gate: contributor opens the file, sees `N pass / 0 fail` in the page title.

## Q9: Splitscreen + Auto mode interaction?
**A**: Since `matchesArrangement` is undeclared, Auto never picks Jumping Tab. Each splitscreen panel can independently set Jumping Tab via its viz picker. Wave C ensures per-panel state.

## Q10: What's `slopsmith#92` referenced in comments?
**A**: A core PR that added the chord-template lookup table to `bundle`. Plugin reads `bundle.chords[i].template` (or similar) to render chord-box without re-deriving shape data.
