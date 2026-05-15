# Analysis — Jumping Tab

## Coverage

| Area | Spec'd | Implemented | Notes |
|---|---|---|---|
| Hopping-ball trajectory tab | yes | yes | core feature |
| Chord-box secondary canvas | yes | yes | from alleexx/renanboni fork |
| Technique capsules + bend arrows | yes | yes | byrongamatos contribution |
| setRenderer registration (slopsmith#36) | yes | yes | `screen.js:1711` |
| Per-instance Wave C state | yes | yes | `createFactory` closure |
| Pure helpers at module scope | yes | yes | `test/test.html` exercises them |
| Demo harness | yes | yes | `demo/index.html?scene=*` |
| Dynamic string count (slopsmith#93) | yes | yes | `bundle.stringCount` |
| Headless screenshot recipe | yes | yes | in README |
| Tests | yes | yes (browser-only) | no CI |
| Settings panel | no | no | called out as future work |
| Mic / scoring | no | no | called out as future work |

## Drift

- Plugin fork lineage is well-documented in README (byrongamatos, alleexx, topkoa, rymarshall). No drift; rather, the README is exemplary at attributing contributions and noting which ones are superseded (topkoa's pane factory by Wave C, rymarshall's WS fix by setRenderer migration).
- `screen.js:48` `DISABLE_RINGS = true` — code path still exists in `drawImpacts`, just short-circuits. Future maintainer reading top-to-bottom might miss the early-return; a clarifying comment alongside `drawImpacts` would help.
- README screenshot regeneration recipe assumes macOS Chrome path — Linux contributors need to substitute `google-chrome`. Cosmetic.

## Gaps

1. **No CI for `test/test.html`.** The harness is excellent and self-contained; running it headlessly via `playwright` or `puppeteer` would gate regressions automatically.
2. **No settings panel.** README calls this out explicitly. Common asks: speed multiplier, palette toggle, visibility window adjustment, ring re-enable.
3. **Trajectory cache N-multiplier under splitscreen** is acknowledged-but-untracked. A diagnostic counter showing cache size per instance would help confirm no leaks.
4. **Headless Chrome path is macOS-specific** in README recipe.

## Recommendations

- **High value**: stand up CI (GitHub Actions) running `test/test.html` via `playwright test` or a simple `puppeteer` harness. The page-title `N pass / 0 fail` is already machine-readable.
- **Medium**: add a settings panel with speed / visibility-window / DISABLE_RINGS toggles. localStorage namespace `jumpingtab_*`. Don't break the existing constants — settings just override them.
- **Low cost**: extend the screenshot recipe to Linux/Windows Chrome paths.
- **Low cost**: add a clarifying comment near `drawImpacts` early-return so the dead-looking code doesn't get accidentally pruned in a future cleanup.
- **Low cost**: a per-instance trajectory-cache size counter exposed via `window.__jumpingtab_diag` would aid splitscreen leak diagnostics.
