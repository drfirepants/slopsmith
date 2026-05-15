# Tasks — Metronome

`[P]` = parallelizable / independent. Existing implementation status
is marked DONE.

## US1 — Audible click on every beat (P1)

- [DONE] T101 Inject toggle button into `#player-controls`
  (`_metInjectButton`).
- [DONE] T102 60 Hz polling loop with `setInterval` and idempotent
  re-eval (`TICK_INTERVAL_ID_KEY`).
- [DONE] T103 Binary-search current beat from `highway.getBeats()`.
- [DONE] T104 ±50 ms tolerance gating to suppress catch-up bursts on
  seek.
- [DONE] T105 Sine envelope click (60 ms) with measure / non-measure
  frequency split (1500 / 1000 Hz).

## US2 — Visual flash (P2)

- [DONE] T201 Register `addDrawHook` on the highway renderer.
- [DONE] T202 Track the highway instance the hook is bound to via
  `DRAW_HOOK_HIGHWAY_REF_KEY` and rebind on renderer swap (with a 1 s
  retry backoff to avoid spinning when the renderer is gone).
- [DONE] T203 Flash alpha decays at ×0.88/frame.
- [DONE] T204 Flash band restricted to y in [0.72H .. 0.90H].
- [DONE] T205 Checkbox toggle (`met-flash-check`).

## US3 — Persistence (P3)

- [DONE] T301 Settings live on a window-scoped object so plugin
  re-evals reuse them.
- [OPEN] T302 [P] Persist settings to `localStorage` (current state:
  in-memory only — README implies persistence). Owner: TBD.

## Cross-cutting / hardening

- [DONE] T401 Idempotent `playSong` wrapper.
- [DONE] T402 Dedupe button injection if `#btn-metronome` already
  exists.
- [DONE] T403 Replace legacy property handlers (`oninput`,
  `onchange`) before adding new listeners — protects against double
  binding from earlier plugin versions.
- [OPEN] T404 [P] Optional: subdivision setting (eighths, triplets).
  Not requested; would increase scope significantly.
- [OPEN] T405 [P] Optional: visual count-in (3-2-1) before a song.

## Tests

- [OPEN] T501 No test harness in repo today. A future task could add a
  `vm`-based test (mirroring `slopsmith-plugin-notedetect/test/`) that
  exercises `_metTick` against a synthetic beat array.
