# Analysis — Base Game Song Extractor

## Coverage

| Area | Spec'd | Implemented | Notes |
|---|---|---|---|
| Status endpoint | yes | yes | `routes.py:44-100` |
| WebSocket extract stream | yes | yes | `screen.js:104-131`, `routes.py` |
| Skip-already-extracted | yes | yes | terminal "All Extracted" branch |
| Auto-cache new metadata | yes | yes | `extract_meta` / `meta_db` from context |
| Missing-source UX | yes | yes | yellow card path |
| RS-dir discovery (3 strategies) | yes | yes | `_find_rs_dir` |
| Tests | yes (open) | no | no test harness in repo |

## Drift

- README mentions "Real-time progress via WebSocket" — matches code.
- `plugin.json` declares `nav.screen = "disc-extract"` (with hyphen). Slopsmith core normalises this to `plugin-disc_extract` for `showScreen`. The JS hook checks for `plugin-disc_extract` (underscore). No bug, but the convention drift is worth flagging in any new plugin docs.
- Hook key uses camelCase variant `__slopsmithDiscExtractHooksInstalled` — fine, but inconsistent with snake_case plugin id. Cosmetic.

## Gaps

1. **No automated tests.** A small fixture PSARC (1-2 songs) would let `disc_extractor.py` regression-test the round-trip without a real Rocksmith install.
2. **WS abort semantics are undocumented.** Server-side behaviour on client disconnect is not asserted in spec or code comments.
3. **No granular extraction.** All-or-remaining only; no per-song extract button despite the per-row UI being a natural fit.
4. **Error reporting is coarse.** Failures during one song bubble up as one error frame; the user can't see "27/56 succeeded, 1 failed, retrying remainder."

## Recommendations

- **Low cost / high value**: add the per-row "extract just this one" button. The plumbing already enumerates per-song extraction inside the loop.
- **Medium cost**: add a small synthetic-PSARC fixture under `tests/` to lock down the wire format of the output.
- **Low cost**: document the WS-disconnect contract in CLAUDE.md / README so future contributors don't accidentally tie session lifetime to extraction lifetime.
- **Cosmetic**: rename hook key to `__slopsmith_disc_extract_hooks_installed` to match plugin id convention (cross-plugin grep ergonomics).
