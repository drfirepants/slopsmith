# Implementation Plan — Section Map

## Architecture

```
slopsmith-plugin-sectionmap/
├── plugin.json   — id, name, version, script (no nav, no screen)
├── screen.js     — single IIFE with poller + DOM injection
├── README.md
└── CLAUDE.md     — speckit stub
```

No backend, no `screen.html`. The plugin manifests with `script` only,
so it runs as a global side-effect script when the plugin loader
mounts it.

## Module breakdown (`screen.js`, 200 lines)

### Constants (lines 8-20)
`SM_COLORS` map from substring → hex color, with a `default`
fallback.

### State (lines 4-6)
```
_smBar       — the DOM node, or null
_smSections  — last-rendered sections array reference
_smDuration  — last-known song duration (cached for input math)
```

### Helpers
- `_smGetColor(name)` (22-28) — substring-match color picker.
- `_smFmt(s)` (167-169) — `mm:ss` formatter for tooltip.

### DOM lifecycle
- `_smCreate()` (30-44) — constructs `#section-map`, attaches
  click + wheel listeners, inserts as first child of `#player`.
- `_smRemove()` (46-51) — removes the DOM node and clears the
  reference.

### Input handlers
- `_smOnClick(e)` (53-74) — pause→seek→resume.
- `_smOnWheel(e)` (76-101) — `deltaY` direction + Ctrl-fine,
  pause→seek→resume.

### Render
- `_smUpdate()` (103-136) — pulls `getSections()`, `getSongInfo()`,
  `getTime()` from `highway`; rebuilds DOM only if `sections`
  reference changed; updates marker position; toggles per-block
  opacity to highlight active.
- `_smRender()` (138-165) — emits one absolute-positioned div per
  section + the playhead `#sm-marker`.

### Side-effects (lines 175-199)
Single guard `__slopsmithSectionMapHooksInstalled` covers:
- `setInterval(_smUpdate, 200)` poller.
- `playSong` wrapper (remove old bar → await orig → create new bar).
- `showScreen` wrapper (remove bar on non-player nav, then delegate).

## Inputs / contracts

### From `window.highway`:
- `getSections() -> Array<{time, name}>`
- `getSongInfo() -> {duration, ...}`
- `getTime() -> number` (seconds)

### From core globals:
- `playSong(filename, arrangement) -> Promise<void>`
- `showScreen(id)` (sync)
- `lastAudioTime` (optional — typeof-checked)

### DOM ids relied on:
- `#player` — bar's mount point.
- `#audio` — seek target.

## Risks

| Risk | Mitigation |
|------|-----------|
| Highway mutates sections array in place | Identity check breaks; would need length-or-deep compare |
| Multiple plugins inserting at top:0 | First child insertion + z-index 5; cooperative |
| User clicks during heavy buffering | Pause-then-seek-on-`seeked` pattern |
| Re-evaluation re-installs side-effects | Single-key idempotency guard |

## Open items

- Section editing [NEEDS CLARIFICATION].
- Touch support [NEEDS CLARIFICATION].
- Color-key ordering for ambiguous matches (clarify Q6).
