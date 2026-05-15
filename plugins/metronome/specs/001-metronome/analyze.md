# Analysis — Metronome Plugin

## Coverage

| Spec area | Implementation | Notes |
|---|---|---|
| FR-001 (toggle button) | `_metInjectButton` | OK — idempotent. |
| FR-002 (60 Hz poll, binary search) | top-level `setInterval` + `_metTick` | OK. |
| FR-003 (50 ms tolerance) | `_metTick` | OK. |
| FR-004 (sine envelope, measure pitch) | `_metClick` | OK. |
| FR-005 (draw hook, alpha decay) | `_metEnsureDrawHookInstalled` + hook | OK — hook re-binds on renderer swap. |
| FR-006 (settings persistence) | `_metSettings` window var | **DRIFT** — no localStorage; survives re-eval, not full page reload. |
| FR-007 (no nav / routes) | `plugin.json` | OK. |
| FR-008 (idempotent re-eval) | `*_KEY` sentinels everywhere | OK. |

## Drift

1. **README implies persistence**, code stores settings in a window
   global only. See FR-006.
2. **README "Toggle button — click 'Metronome' in the player controls
   to enable/disable"** — accurate, but does not mention the volume
   slider or flash checkbox that appear when enabled. Minor doc gap.

## Gaps

1. No test harness. The plugin sibling `slopsmith-plugin-notedetect`
   uses a Node `vm` loader for unit tests; the same pattern could
   exercise `_metTick` here.
2. No subdivision support — single click per beat. Some users will
   want eighth-note clicks for slow songs.
3. No visual count-in. Songs with no lead-in beats start the click
   abruptly on the first downbeat.
4. The 60 Hz poller runs forever once the script loads, even when no
   song is playing. Cost is trivial (binary search on a possibly
   empty array, plus a missing-`highway` early-return), but it's
   non-zero.

## Recommendations

1. **Persist settings** — add `localStorage.setItem` in
   `_metSetVolume` / the flash change listener and a corresponding
   `getItem` block when initializing `_metSettings` (T302). Closes
   FR-006 drift.
2. **Document the slider/flash UI** in README under "Features".
3. **Keep the plugin's footprint exactly as-is otherwise.** Adding
   subdivisions or count-ins would push the plugin past its
   "single-purpose" constitutional principle. If those features are
   wanted, they belong in a sibling plugin (or the editor plugin).
4. **Consider a tiny vm-based test** that asserts `_metTick`
   produces a click at expected times for a synthetic beat array.
   Would catch regressions in the seek-tolerance logic.
