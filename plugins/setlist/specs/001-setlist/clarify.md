# Clarifications — Setlist Builder

## Q1: Why is `position` 1-based, not 0-based?
**A**: It is initialized as `MAX(position) + 1` (`routes.py:127-130`)
where the seed is `COALESCE(MAX(position), 0) + 1`, yielding 1 on
empty setlists. The wire shape is consistent across endpoints. The
1-based choice is also more user-friendly when surfaced in UI.

## Q2: How does reorder handle a missing or extra song id?
**A**: `routes.py:166-170` UPDATEs only rows matching `id=? AND
setlist_id=?`. Extra ids are no-ops; missing ids leave their position
unchanged. There is no validation that `len(song_ids) ==
COUNT(*)`. [NEEDS CLARIFICATION: should the route 400 on length
mismatch?]

## Q3: Why does the frontend prompt for the new name with `prompt()`?
**A**: Minimal v1 implementation (`screen.js:33, 99`). A real modal
would require a custom dialog system; the host has none today. UX
debt acknowledged.

## Q4: What if the user clicks Play All on an empty setlist?
**A**: `slPlayAll` short-circuits if `data.songs.length === 0`
(`screen.js:176`). The button is also hidden when the setlist is
empty (`screen.js:75-76`).

## Q5: What if the host's `<audio>` element has multiple `ended`
listeners?
**A**: We add one listener per script load (`screen.js:243-249`).
Re-evaluation grows the listener list because there is no removal.
The idempotency guard
(`__slopsmithSetlistHooksInstalled`, `screen.js:260-262`) covers the
`showScreen` wrap but NOT the `audio` listener registration block,
which lives in a separate IIFE outside the guard.
[NEEDS CLARIFICATION: move the audio listener inside the guard.]

## Q6: How is HTML escaping handled in dynamic content?
**A**: The `esc()` function is provided by core; the plugin assumes
it. All `${esc(...)}` interpolations use it (`screen.js:23, 86,
148-154` etc.). If `esc` is missing, the plugin would inject raw
title/artist into innerHTML.

## Q7: Why store the arrangement name as a string, not as the
arrangement index?
**A**: Indices change as the source PSARC's arrangement order shifts
across re-encodes; names like "Lead", "Rhythm" are stable. Trade-off:
two arrangements named "Lead" on the same song would be ambiguous.

## Q8: What happens to an already-loaded queue if the user navigates
to a different screen?
**A**: Nothing — `_slQueue` and `_slQueueIndex` persist. The overlay
remains visible (it's `position: fixed` in `body`) so the user can
still hit Stop. Navigating to `plugin-setlist` reloads the list view
without affecting the queue.
