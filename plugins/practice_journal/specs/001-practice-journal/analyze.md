# Analyze — Practice Journal

## Coverage

| Area | Implementation | Tests | Spec coverage |
|------|---------------|-------|---------------|
| Auto-tracking | `screen.js:15-99` | None | FR-1..5 |
| Dashboard | `screen.js:111-198`, `routes.py:80-145` | None | FR-6 |
| Per-song detail | `routes.py:147-187` | None | FR-7 |
| Schema/migrations | `routes.py:19-39` | None | NFR-1, FR-1 |

There are no automated tests in this repo (no `tests/`,
`requirements-test.txt`, or CI workflow). All verification is manual.

## Drift

1. **Schema is duplicated**: `profileimport/routes.py:391-405` re-creates
   the same `practice_sessions` table. If we add a column here without
   propagating, profileimport's `INSERT` will fail at runtime.
2. **`/song/{filename:path}` is dead code**: spec'd and shipped, but the
   dashboard never calls it.
3. **CLAUDE.md is the speckit stub** — no agent-facing summary of the
   plugin's behavior.
4. **README.md** describes "Per-song history" as a feature, but only
   the API exists; the UI does not.

## Gaps

- No test coverage anywhere.
- No telemetry on dropped/short sessions — silent failures by design.
- UTC vs local-time aggregation is undocumented in user-facing copy.
- `loops_used` carries display names which are not stable identifiers.
- No backup / export of `practice_journal.db`.

## Recommendations

1. **Add minimal tests**: round-trip `POST /session` → `GET /stats`,
   schema-creation idempotency, lock-correctness under threads.
2. **Lift schema into a shared module** that both this plugin and
   profileimport import — eliminates drift at the source.
3. **Wire the per-song detail endpoint** into a click-to-expand row
   on the recent-sessions list to retire dead code.
4. **Document UTC behavior** in README, or convert to local-time using
   the host's known timezone (none available today).
5. **Switch to stable loop IDs** in `_pjLoopsUsed` — requires core to
   expose loop IDs in the saved-loop dropdown's `data-` attributes.
6. **Replace CLAUDE.md stub** with a one-pager pointing at this spec
   directory.

## Risk assessment

- **Low–medium**: writes are concurrent-safe (lock + WAL), failures are
  fire-and-forget, schema is forward-only. Main risk is silent data
  loss from network drops.
- **Cross-plugin coupling**: medium. The profileimport plugin's tight
  link to our DB is the most fragile contract; any schema change must
  be coordinated.
