# Analyze — Section Map

## Coverage

| Area | Code | Tests | Spec |
|------|------|-------|------|
| DOM lifecycle | `screen.js:30-51` | None | FR-2 |
| Click seek | `screen.js:53-74` | None | US-2 |
| Wheel scrub | `screen.js:76-101` | None | US-3 |
| Render | `screen.js:103-165` | None | US-1, US-4 |
| Side-effects | `screen.js:175-199` | None | US-5, FR-1, FR-5 |

No tests, no CI workflow.

## Drift

1. **`SM_COLORS` ordering**: ambiguous names like "Solo Verse" match
   the first key by enumeration order. Currently `verse` precedes
   `solo`; this is implicit and not codified.
2. **README** mentions "white marker shows current position" — the
   marker is white but the README does not say it's only 2px wide
   with a pointer-events:none rule. Acceptable.
3. **CLAUDE.md is the speckit stub**.
4. **Visual height** is 20px constant — has no setting in
   `plugin.json` despite the host theming surface elsewhere.

## Gaps

- No test coverage. Even a JSDOM smoke test for
  `_smRender` would catch CSS regressions.
- No keyboard accessibility — the bar is mouse-only.
- No screen-reader semantics on section blocks (no role / aria-label).
- No theming hooks — colors are hard-coded.
- No protection against `getSections()` returning thousands of
  sections (a malicious or malformed chart would render thousands of
  divs); on real charts this is fine.

## Recommendations

1. **Re-order `SM_COLORS`** so `solo`, `bridge`, `breakdown`,
   `pre`, `noguitar` are checked before generic `verse`/`chorus` to
   bias multi-word names correctly (clarify Q6).
2. **Expose colors as CSS variables** (e.g. `--sm-color-verse`) so
   themes can override without forking.
3. **Add aria labels** on each section block for screen-reader users
   (label includes the section name + start time).
4. **Subscribe to a sections-changed event** if/when core emits one;
   reduce polling to 0.
5. **Make height/opacity configurable** via a small `settings.html`
   if the plugin grows.
6. **Replace the speckit-stub CLAUDE.md** with a one-page agent guide.

## Risk assessment

- **Low**: small surface, no backend, no persistence.
- **Failure modes**: cosmetic — wrong color, mis-positioned block,
  or temporarily wrong active highlight. None block playback.
