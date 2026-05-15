# Clarifications — Practice Journal

## Q1: What defines "session start" and "session end"?
**A**: Start = the wrapped `playSong` call assigning `_pjSessionStart`
**after** awaiting the original (`screen.js:26-38`). End = any
subsequent `showScreen(id)` where `id !== 'player'` (including
`plugin-practice_journal` itself), `playSong` of another song (which
calls `_pjEndSession()` first), or `beforeunload`.

## Q2: Why is the 5-second floor enforced server-side, not client-side?
**A**: To make the policy authoritative even if a future client forgets
it. `routes.py:57-58` drops short sessions and returns
`{"ok": True, "skipped": True}` so the client cannot tell from a 200
response that nothing was recorded.

## Q3: How is `today_time` computed?
**A**: `routes.py:84-95`. `today` is the UTC date string `YYYY-MM-DD`;
the WHERE clause is `started_at >= ?`. Sessions whose `started_at`
ISO timestamp begins with that date string are counted. This is
**UTC-based**, so a user practicing past local midnight may see
splits across two days. [NEEDS CLARIFICATION: should aggregation be
local-time? Currently it is not.]

## Q4: Who else writes to `practice_journal.db`?
**A**: The `profileimport` plugin opens the same DB file directly to
seed synthetic sessions from imported Rocksmith profile data
(see profileimport's `routes.py:387-405`). The schema in both
plugins is duplicated; **practice_journal is the source of truth** —
profileimport must follow.

## Q5: What happens if the four host globals are missing?
**A**: `screen.js:25-29` references them by name and re-assigns. If
`window.playSong` is undefined, the wrapper assigns
`async function(...) { ... await origPlaySong(...) }` where
`origPlaySong` is undefined → `TypeError` on first invocation. Core
is assumed to expose all four. There is no defensive check.

## Q6: How is `avg_speed` rounded and why?
**A**: `screen.js:88` rounds to 2 decimal places with
`Math.round(avgSpeed * 100) / 100`. This mirrors the slider's
granularity; deeper precision would inflate row sizes without
analytic value.

## Q7: Is loop usage tracked as IDs or display names?
**A**: Display names. `screen.js:62` strips trailing `(...)` from
`opt.textContent`. This makes the journal robust to loops being
deleted/recreated with the same name but loses true identity.
[NEEDS CLARIFICATION: should we record the loop's stable ID instead
to support per-loop analytics?]

## Q8: How are dashboard counts deduplicated by song?
**A**: `unique_songs` is `COUNT(DISTINCT filename)` (`routes.py:103-105`).
Different arrangements of the same file count as one song; this is
intentional to match user mental model ("songs practiced") but loses
arrangement granularity for `top_songs`.
