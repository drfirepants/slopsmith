# Clarifications — Band Studio

## Q1 — Why two recording modes (highway vs mixer)?
**Resolved.** Highway recording lets the player perform along with the chart
visualiser they already use for practice. Mixer recording is the "DAW-style"
mode where they can hear all takes and adjust before/while recording. Both
upload via the same endpoint and follow the same drift-correction pipeline
(constitution §II).

## Q2 — Why does the server convert webm to WAV?
**Resolved.** webm duration metadata is unreliable across browsers (Chrome
typically reports `Infinity` until you seek to the end). WAV gives ffprobe an
accurate duration, which is the input to drift correction. Converting once,
server-side, also keeps the rest of the pipeline format-agnostic.

## Q3 — Why is drift correction set at 0.05%?
**Resolved.** Below this, drift is below the threshold of musical perception
on typical takes (it accumulates ≤ 100 ms over a 3-minute song). Above it,
late notes start sounding loose. Constant in `routes.py` upload handler.

## Q4 — How are mix parameters kept consistent between Web Audio and ffmpeg?
**Resolved.** Both render from the same `studio_mix_settings` row. The
mapping (e.g. `volume = 1.5` → ffmpeg `volume=1.5`) is conventional and
linear. Equivalence is enforced by ear today. See constitution §I.

## Q5 — Why a generated 2 s room IR rather than a curated set?
**Resolved.** Keeps the plugin self-contained — no IR licensing, no asset
shipping. The IR is generated procedurally on first `_createReverbBus` call.
Users wanting bespoke verbs export and process externally.

## Q6 — Why `DynamicsCompressor` for the master limiter rather than a
brick-wall implementation?
**Resolved.** The Web Audio API offers no native brick-wall. Configuring
`DynamicsCompressor` with high ratio + threshold near 0 dBFS approximates a
limiter for client preview. The export side uses ffmpeg `alimiter` for a
sharper limit if needed (verify in `routes.py`).

## Q7 — Why is undo a stringified-state stack rather than a command log?
**Resolved.** Mix state is small (~hundreds of bytes per snapshot). String
diffs are cheap and dedup is trivial. Command logs would be more efficient
for large sessions but add a layer of bug surface for marginal benefit at 50
entries.

## Q8 — What governs idempotency of the install?
**Resolved.** `window.__slopsmithStudioHooksInstalled` and
`…Installing` flags wrap the entire IIFE. See `screen.js` top comment for
the full failure mode (chain growth, duplicate keydown, closure leak).

## Q9 — Why is Demucs separated as a remote service?
**Resolved.** Demucs needs PyTorch + ~3 GB of model weights + ideally a GPU.
Slopsmith runs on a Docker host or NAS that may not have any of those. The
remote service architecture (`slopsmith-demucs-server`) keeps the heavy
runtime out of the Slopsmith container. See README "Demucs Server Setup".

## Q10 — Open: what happens when ffmpeg is unavailable?
**Open.** The Docker image bundles ffmpeg/ffprobe. `slopsmith-desktop` may not.
Today the upload pipeline raises (HTTP 500) with the subprocess error. A
clearer "ffmpeg required" detection at startup would be friendlier.

## Q11 — Open: concurrent edits?
**Open.** Two browsers modifying the same session race on
`POST /mix-settings`. Last write wins (no version stamp). Acceptable for
single-user sessions; a problem for "collaborative" claims in the README.
