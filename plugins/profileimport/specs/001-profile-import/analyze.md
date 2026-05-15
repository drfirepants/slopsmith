# Analyze — Profile Import

## Coverage

| Area | Code | Tests | Spec |
|------|------|-------|------|
| Decrypt | `routes.py:59-94` | None | FR-1 |
| Preview | `routes.py:97-156`, `screen.js:57-104` | None | FR-2 |
| Mapping | `routes.py:165-178, 242-318`, `screen.js:108-175` | None | FR-3, FR-4 |
| Import | `routes.py:180-204, 321-601`, `screen.js:179-274` | None | FR-5..10 |
| History | `routes.py:206-219`, `screen.js:290-317` | None | US-4 |
| play-stats endpoint | `routes.py:221-235` | None | (unused) |

No test suite, no CI workflow, no `tests/` directory.

## Drift

1. **Practice-journal schema duplication**: `routes.py:391-405`
   re-creates `practice_sessions`. If practice_journal evolves the
   schema, this plugin breaks silently on next import.
2. **`/play-stats` endpoint is dormant**: returns top 100 plays but
   nothing renders it.
3. **Vocals exclusion is asymmetric**: mapping skips Vocals, but
   `Stats.Songs` may still include Vocals PIDs that won't match
   anything → counted in `total` but not in `matched`. Acceptable but
   mildly confusing in progress messages.
4. **CLAUDE.md is the speckit stub**.
5. **`_stashed_profiles` is unbounded** — pathological re-uploads
   could grow memory.

## Gaps

- No tests around the EVAS format (magic / truncated / bad checksum
  cases).
- No tests around the favorites/playcounts/scores import paths.
- No mutex on import; two clients can race.
- No retry on WebSocket drops mid-import; the user re-runs.
- No reporting of which favorites / songs were unmatched (only counts).
- Profile data is held in memory only; if the server crashes, the
  user must re-upload.

## Recommendations

1. **Add a focused test suite**: golden EVAS fixture (small, scrubbed),
   schema migration, batch-insert correctness, synthetic-session
   row shape.
2. **Lift `practice_sessions` schema** into a shared module (or add
   a tiny `practice_journal.api` HTTP endpoint that this plugin POSTs
   to instead of writing the DB directly). The HTTP indirection would
   eliminate the schema-coupling risk entirely.
3. **Add `/api/plugins/profileimport/unmatched`** endpoint listing
   PIDs the import couldn't map to filenames — actionable for users
   debugging missing CDLC.
4. **Implement an import mutex** keyed on `profile_id` to prevent
   concurrent races (clarify Q9).
5. **Stashed-profile TTL**: evict after 30 minutes; document in
   constitution.
6. **Wire `/play-stats`** into a library overlay (e.g. play-count
   chip on each card) so the data isn't dead.
7. **Replace CLAUDE.md** with a one-pager.

## Risk assessment

- **Medium**: cross-plugin schema coupling and concurrent-import
  race are real but rarely-triggered in single-user setups.
- **Crypto risk is bounded**: the AES-ECB usage is dictated by the
  on-disk format; it is not a security boundary the plugin chose.
- **Operational risk**: a long mapping scan (10k+ PSARCs) blocks the
  event-loop momentarily during each batch despite `await
  asyncio.sleep(0)` — fine for now, may need offload to thread pool
  if libraries grow further.
