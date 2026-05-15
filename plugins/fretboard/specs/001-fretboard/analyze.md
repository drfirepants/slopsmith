# Analysis — Fretboard View

## Coverage

| Area | Spec'd | Implemented | Notes |
|---|---|---|---|
| Toggle overlay | yes | yes | `screen.js:24-53` |
| Canvas + dismiss UI | yes | yes | sibling pattern for pointer-events |
| Active-note window | yes | yes | ±80 ms |
| Sustain fade | yes | yes | alpha 1→0.3 |
| Rocksmith string colors | yes | yes | matches palette |
| DPR scaling | yes | yes | |
| 6-string / 24-fret layout | yes | yes | hard-coded |
| Bass / extended-range | no | no | gap |
| Persistence | no | no | gap |
| Tests | yes (open) | no | |

## Drift

- README implies the overlay "fades through their sustain duration" — implementation matches.
- Code uses `window` as a local variable name in `_fbGetActiveNotes` (`const window = 0.08;`) which shadows the global. Not a bug here (no `window.X` access inside that function) but a footgun for future edits.
- Plugin uses the legacy `playSong` wrap pattern, while the drums and jumpingtab plugins use Wave C setRenderer. Intentional — it's an overlay, not a renderer — but worth documenting so future maintainers don't try to "modernise" it incorrectly.

## Gaps

1. **Hard-coded 6 strings.** Bass arrangements display correctly only on the bottom 4 lanes; bottom 2 stay empty. Extended-range guitars (7/8) are clipped silently. Reading `bundle.stringCount` (slopsmith#93) — when the highway exposes it — would let the layout adapt.
2. **No persistence.** `_fbEnabled` resets on every browser reload; users have to re-toggle.
3. **No tuning display.** The fret numbers are absolute; users tuning in Drop D / Open G have to mentally translate. Showing the tuning name in a corner would help context.
4. **No tests.** `_fbGetActiveNotes` is a pure function ideal for a test harness like jumpingtab's.
5. **Variable name `window` shadows global.** Cosmetic but a subtle hazard.

## Recommendations

- **Low cost / high value**: rename local `window` → `WINDOW_SECONDS` in `_fbGetActiveNotes`. Trivial defensiveness.
- **Low cost**: persist `_fbEnabled` to localStorage as `fretboard_enabled`.
- **Medium**: dynamic string count via `bundle.stringCount` (or via inspecting `highway.getNotes()` for max string seen). Adapt `FB_STRINGS` per song.
- **Low cost**: read tuning from `highway` if exposed and render as a corner label.
- **Low cost**: stand up `test/test.html` with a synthetic notes/chords list verifying the active-note window math.
