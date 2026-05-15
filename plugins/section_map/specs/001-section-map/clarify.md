# Clarifications — Section Map

## Q1: Why a 200ms poller instead of an event-driven update?
**A**: `highway` does not expose a `sections-changed` event today.
Polling at 200ms is cheap (a length compare + identity compare) and
keeps the plugin decoupled from internal highway events. If core
later emits an event, the poller can be removed and replaced with
a listener.

## Q2: Why is `sections !== _smSections` enough to detect change?
**A**: Highway returns the same array reference for the same song;
loading a new song produces a new array. This identity check avoids
deep equality on every tick. If highway ever mutates the array
in-place, this would break — currently it does not.

## Q3: Why `lastAudioTime` if it's undefined?
**A**: `typeof lastAudioTime !== 'undefined'` (`screen.js:62`)
guards an optional global. Some core builds expose
`lastAudioTime` as a leak detector for spurious time jumps;
keeping it in sync with our seek prevents the detector from firing.
On builds without the global, the line is a no-op.

## Q4: How are section names displayed (cleanup pipeline)?
**A**: `screen.js:151-152`:
```js
let label = sec.name.replace(/\d+$/, '').trim();
label = label.charAt(0).toUpperCase() + label.slice(1);
```
Trailing digits (`verse2`, `chorus3`) are stripped; the first letter
is upper-cased. This loses the `2`/`3` ordinal but reduces visual
clutter on narrow blocks.

## Q5: Why does the wheel handler not use Pointer Events / passive listeners?
**A**: It calls `e.preventDefault()` (`screen.js:78`) so it must be
non-passive (`{passive: false}` at line 43). Pointer events would
add cross-platform complexity not currently needed.

## Q6: Section colors are substring-matched — what if a chart names a section "Solo Verse"?
**A**: First match wins (`Object.entries(SM_COLORS)` order:
intro/verse/chorus/...). "Solo Verse" matches `verse` first since
`SM_COLORS` enumeration order in the source has `verse` before `solo`.
[NEEDS CLARIFICATION: should we order more-specific keys first
(e.g. `solo` before `verse` to bias "Solo Verse" to red)?]

## Q7: What happens when the user clicks during a paused state?
**A**: `wasPlaying = !audio.paused` is false, so the click handler
seeks immediately and does not re-trigger `play()`
(`screen.js:67-73`). This is correct; pausing twice is harmless.

## Q8: Why does `_smCreate` insert as the first child of `#player`
instead of using a fragment after the HUD?
**A**: To guarantee the bar sits at top:0 above the HUD
without managing z-index for sibling overlays. The 20px height was
chosen to not overlap typical HUD elements; on tall HUDs the user
sees a tight strip above the HUD, which is acceptable.
