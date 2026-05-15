# Analyze — Split Screen

## Coverage

| Area | Code | Tests | Spec |
|------|------|-------|------|
| Layouts | `screen.js: LAYOUTS, applyLayoutStyle` | None | US-1, US-2 |
| Panel lifecycle | `createPanel`, `initPanel`, `teardownPanels` | None | FR-2, FR-8 |
| Time sync | `startTimeSync` / `stopTimeSync` | None | FR-3 |
| Sizing | `sizeCanvases` | None | FR-6, NFR-1 |
| External integration | capability checks in `populateSelect`, `initPanel` | None | FR-4 |
| Persistence | `savePanelPrefs`, `loadPanelPrefs`, `captureCurrentPrefs` | None | FR-5 |
| Pop-out | `popups`, `FOLLOWER`, `_ssChannel` | None | FR-7, US-6, US-7 |
| Detect | `toggleDetect`, `cycleDetectChannel` | None | FR-9 |
| `_onReady` race | `playSong` wrapper poll | None | FR-10 |

No unit tests in the repo. CLAUDE.md provides a "Testing Checklist"
(README "Testing Checklist") which is a manual smoke list.

## Drift

1. **README and CLAUDE.md duplicate the integration contract** (Path
   1 / Path 2). Risk of divergence over time. CLAUDE.md is more
   precise about lifecycles; README is more user-facing.
2. **`screen.js` is 2544 lines** in a single IIFE. Internal banner
   comments help, but there's no module separation.
3. **Pop-out config is URL-encoded** rather than passed via
   `postMessage` after open. Acceptable but unusual; the URL becomes
   long for complex panels.
4. **Plugin load-order is implicit** (alphabetical). Splitscreen
   relies on this for `_onReady` race assumptions but can't enforce it.
5. **The "Always enter split screen" + "Remember between songs"
   booleans interact** — both can be true; the resulting precedence
   isn't documented in settings.html copy.

## Gaps

- **No automated tests**: with 2544 lines the manual surface is large.
  At minimum a JSDOM smoke test on `applyLayoutStyle` and
  `sizeCanvases` would catch regressions.
- **No version negotiation** with external plugins: they're
  capability-checked but not version-checked. A breaking change in
  e.g. the 3D highway factory shape would crash a panel.
- **No telemetry** when a user reports drift / freeze in popups.
- **Popup main-closed freeze** is documented but not handled
  programmatically.
- **No way to broadcast a "dock all" command** from main to popups.

## Recommendations

1. **Split `screen.js` into bands** demarcated by giant `// ── X ─`
   banners (already partially done). Future: introduce a lightweight
   namespace pattern (a `splitscreen` IIFE-returned object) that
   internal sections share via closure rather than file-level
   variables — would aid debugging without a build step.
2. **Version-tag external plugin factories**: have plugins also expose
   `window.<factory>.contractVersion` and check it before use.
3. **Self-dismiss popups on main close**: detect via
   `BroadcastChannel('slopsmith-ss')` heartbeat absence (e.g. >3s
   without a tick) and close the popup with a friendly message
   (clarify Q10).
4. **"Dock all" in main**: send a `dock-all` message over the
   BroadcastChannel; popups respond by dispatching their `dock`
   handler.
5. **Add a runtime self-test page** under
   `/api/plugins/splitscreen/_test` that exercises Path 1 + Path 2
   with synthetic factories.
6. **Document interaction of Always + Remember booleans** in
   `settings.html` copy.
7. **Codify the integration contract once**: choose either README or
   CLAUDE.md as canonical and have the other link to it.

## Risk assessment

- **High surface area, low backend risk**: no DB, no server. Failure
  modes are visual / UX (panels don't appear, sizes wrong, popups
  freeze).
- **Cross-plugin coupling is the highest risk**: visualization and
  pane plugins assume specific factory shapes. A core release that
  changes `setRenderer` semantics would break splitscreen and every
  visualization plugin simultaneously.
- **Pop-out is the most fragile path**: depends on browser popup
  permissions, BroadcastChannel availability, and matching origins.
