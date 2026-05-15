# Analysis — Drum Highway

## Coverage

| Area | Spec'd | Implemented | Notes |
|---|---|---|---|
| 8-lane drum view | yes | yes | `screen.js` |
| MIDI input | yes | yes | Chrome / Edge |
| Custom mapping | yes | yes | with hardened validator |
| Built-in sounds | yes | yes | WebAudioFont GM kit |
| Hit detection | yes | yes | ±50 ms |
| Auto-activate for drums | yes | yes | word-boundary regex |
| Splitscreen multi-instance | yes | yes | Wave C |
| Tests | yes (open) | no | no test harness |

## Drift

- `plugin.json` declares `"type": "visualization"`. The setRenderer contract uses `window.slopsmithViz_drums`. Naming is consistent.
- README lane table matches `DRUM_LANES`.
- Comment block at top of `screen.js` accurately documents Wave B → Wave C transition; no drift between intent and implementation visible from skim.

## Gaps

1. **No test harness.** `screen.js` has many pure helpers (custom-mapping validator, lane mapping, hit-window math) that would benefit from a `test/test.html` similar to the jumpingtab plugin's.
2. **No latency calibration.** Real e-kit setups have 5-30 ms latency depending on USB stack; the ±50 ms window absorbs this but the user has no way to compensate.
3. **No score persistence.** Streak / accuracy are session-only; no per-song history.
4. **One drum kit only.** The README notes WebAudioFont GM, but there's no kit selector despite the trivial cost of swapping presets.
5. **Documentation drift between README and CLAUDE.md.** CLAUDE.md is the speckit stub — it points at "the current plan" but no plan existed before this doc set.

## Recommendations

- **Low cost / high value**: extract the custom-mapping validator + hit-window math into a `test/test.html` along the lines of jumpingtab's. The validator is security-relevant (prototype-pollution resistance).
- **Medium cost / high value**: kit selector (acoustic / electronic / 808) — three preset URLs, one localStorage key, a select in the settings panel.
- **Medium cost / medium value**: per-song score persistence keyed by song id + arrangement (`drums_score_<songId>` with high-water-mark accuracy).
- **Low cost**: latency calibration offset slider in settings, applied to the hit-window math.
- **Cosmetic**: populate CLAUDE.md with a pointer to `specs/001-drums/plan.md` so future agents land on the right doc.
