# Slopsmith Plugin: Sloppak Converter

A plugin for [Slopsmith](https://github.com/byrongamatos/slopsmith) that converts Rocksmith PSARC customs into the open `.sloppak` song format right from the library, with optional [Demucs](https://github.com/facebookresearch/demucs) stem splitting. Conversion runs as a background job queue — kick off a job and keep playing, browsing, or queueing more while it works.

## Features

- **Bulk select + convert** — toggle Select mode in the library, tick whichever PSARCs you want, and queue them in one click. Selection survives filter changes and reloads.
- **"Convert all PSARCs missing a sloppak (in current view)"** — server walks the library, intersects with what's already on disk, and queues just the gaps. Honors your active search / format / tuning / favorites filters.
- **Conversions dashboard** — dedicated nav tab with a live job queue: state filter chips, per-job state badge, progress bar, song metadata (artist / title / album / duration / tuning / arrangement chips), and a post-conversion result line on done jobs (stems Demucs produced, output size, elapsed time). Header has Pause/Resume, Cancel all queued, Retry failed, Clear finished.
- **Pause / resume the queue** — stop processing without losing what's queued. The currently-running job finishes; new jobs sit until you resume.
- **Convert button on every PSARC library card** — one click still enqueues a single job
- **Floating progress panel** — active jobs and their stage (extracting → splitting → packing) shown live in the lower-right, with `Open queue →` and `×` dismiss controls. Dismissal auto-resets when a fresh job arrives so you don't miss new work.
- **Reload-stickiness** — if you're on the Conversions tab when you refresh the browser, you stay on it instead of bouncing back to Library.
- **Serial job queue** — one conversion at a time, so Demucs doesn't fight itself for CPU
- **Live progress over WebSocket** — every connected tab sees the same job state in real time
- **Automatic library refresh on completion** — the new `.sloppak` appears in the library grid without a manual rescan
- **Optional Demucs stem splitting** — splits the mixed audio into guitar / bass / drums / vocals / piano / other using `htdemucs_6s`. Falls back to a single-stem sloppak if Demucs isn't installed.
- **Output isolation** — generated sloppaks land in `DLC_DIR/sloppak/` so they stay separate from your source CDLC

## Installation

> **Important:** This plugin must be installed inside a running [Slopsmith](https://github.com/byrongamatos/slopsmith) instance. It depends on the core `lib/sloppak_convert.py` module provided by the host app — it will not work as a standalone project.

```bash
cd /path/to/slopsmith/plugins
git clone https://github.com/topkoa/slopsmith-plugin-sloppak-converter.git sloppak_converter
docker compose restart
```

On first boot the plugin's `requirements.txt` installs `torch`, `torchaudio`, and `demucs` (CPU wheels) into Slopsmith's persistent `/config/pip_packages` volume. This is a ~1.2 GB download and can take several minutes the first time — subsequent restarts are instant thanks to the install marker.

Model weights (~50 MB per model) cache to `/config/torch_cache` so they're not re-downloaded on container rebuild.

## Usage

1. Open the library.
2. Click **Convert** on any PSARC card. The button shows `Queued → extracting → splitting → packing → ✓ Converted`.
3. A floating panel in the lower-right tracks every active job. Keep playing other songs; conversion runs out-of-band.
4. When the job completes, the library refreshes automatically and the new `.sloppak` appears. Use the companion [Stems](https://github.com/topkoa/slopsmith-plugin-stems) plugin to mix its stems live during playback.

PSARCs whose tuning is not E Standard will convert fine — use the core Retune feature on the original PSARC first if you want to normalize tuning before converting.

## How it works

### Backend (`routes.py`)

A single-worker asyncio queue:

- `POST /api/plugins/sloppak_converter/enqueue  {filename, split, reconvert?}` — schedules a single job (legacy wire shape preserved for the per-card / per-row buttons)
- `POST /api/plugins/sloppak_converter/enqueue_bulk  {filenames, split, reconvert}` — schedules many; returns `{enqueued, skipped}` with per-item reason codes (`already_queued`, `already_running`, `already_converted`, `not_found`, `not_psarc`)
- `GET  /api/plugins/sloppak_converter/missing_sloppak?<library filter querystring>` — PSARCs in the user's current view that don't have a paired sloppak yet
- `POST /api/plugins/sloppak_converter/cancel_queued` — flip every queued job to cancelled (running untouched)
- `POST /api/plugins/sloppak_converter/retry_failed` — re-enqueue every error job as a fresh job; old error rows preserved
- `POST /api/plugins/sloppak_converter/clear_finished` — evict `done | error | cancelled` jobs
- `POST /api/plugins/sloppak_converter/pause` / `POST .../resume` — gate the worker without losing queued work
- `GET  /api/plugins/sloppak_converter/jobs` — current state of all jobs (+ `paused` + `demucs_available`)
- `DELETE /api/plugins/sloppak_converter/jobs/{id}` — cancel a queued (not running) job
- `WS  /ws/plugins/sloppak_converter/events` — snapshot on connect plus live `job_update` and `queue_state` broadcasts

The worker runs the actual conversion in a thread-pool executor and pushes progress updates via `loop.call_soon_threadsafe`, so the asyncio loop stays responsive. The conversion pipeline itself lives in the Slopsmith core repo at `lib/sloppak_convert.py`:

1. **Extract** — unpack the PSARC, parse arrangements, decode audio
2. **Convert** — WEM → OGG via `vgmstream-cli` → `ffmpeg libvorbis`
3. **Write** — manifest.yaml, arrangements/*.json, lyrics.json, cover.jpg, stems/full.ogg
4. **Split** (optional) — shell out to `python -m demucs -n htdemucs_6s` and repackage the 6 split stems, removing `full.ogg`
5. **Pack** — zip the directory (or emit directory form) into `DLC_DIR/sloppak/<name>.sloppak`

### Frontend (`screen.js`)

Injects a Convert button into every library card via a `MutationObserver` that coalesces DOM updates through `requestAnimationFrame` (so button re-renders don't retrigger the observer). The floating panel renders from job state held in a `Map` keyed by filename, re-rendering on every `job_update` and pruning completed jobs after a short TTL.

## Demucs notes

- **CPU-only by default** — the bundled requirements use the pytorch CPU wheel index. A 3–4 minute track takes roughly a minute to split on a modern 8-core CPU.
- **GPU-accelerated alternative** — for faster stem splitting, you can use the standalone [Slopsmith Demucs Server](https://github.com/byrongamatos/slopsmith-demucs-server) which runs on a separate machine with a CUDA GPU. It provides GPU-accelerated source separation via a REST API and also supports lyrics alignment via Whisper.
- **Fallback** — if Demucs fails to import at runtime (e.g. install still in progress), the plugin reports `demucs_available: false` in its snapshot and the Convert button falls back to producing a single-stem sloppak with a visible warning. The user can re-run the job later once Demucs is available.
- **Model choice** — `htdemucs_6s` is the 6-source variant that includes guitar and piano as distinct outputs, which is what guitar-focused Slopsmith users want. Swap it by editing `split_sloppak_stems(..., model="...")`.

## Requirements

- Slopsmith with `.sloppak` format support and the `lib/sloppak_convert.py` module (available on the `feature/sloppak-format` branch and its merged descendants)
- **Slopsmith core with the demucs subprocess `torchaudio.save` → `soundfile` shim** ([byrongamatos/slopsmith#203](https://github.com/byrongamatos/slopsmith/pull/203), shipped in versions newer than 0.2.4). This plugin (1.0.2+) drops the `torchcodec` dependency that recent torchaudio routes `.save()` through; without the core shim the demucs subprocess crashes at the first stem write with `ImportError: TorchCodec is required for save_with_torchcodec`. Pin the plugin to `<= 1.0.1` if you must run on an older core.
- Python 3.10+ with `vgmstream-cli` and `ffmpeg` on `PATH` inside the Slopsmith container (already provided by the standard Slopsmith Docker image)
- ~2 GB free disk in the persistent `/config` volume for torch + demucs + model weights

## Testing

Tests live in `tests/` and stub the heavy `convert_psarc_to_sloppak` / `split_sloppak_stems` calls so they don't actually shell out to Demucs. The `routes.py` module imports from the host's `lib/`, so the test runner needs a Slopsmith checkout on disk. All transitive deps (`pycryptodome`, `pyyaml`, etc.) are included in `requirements-test.txt`:

```bash
# Install test requirements:
pip install -r requirements-test.txt

# Either set SLOPSMITH_ROOT explicitly:
SLOPSMITH_ROOT=/path/to/slopsmith pytest tests/ -v

# …or place the host as a sibling at ../slopsmith and just run:
pytest tests/ -v
```

GitHub Actions runs the suite on every PR (`.github/workflows/test.yml`); it clones byrongamatos/slopsmith next to this repo automatically.

## Other Plugins

- [Stems](https://github.com/topkoa/slopsmith-plugin-stems) — live multi-stem mixer for the `.sloppak` files this plugin produces

## License

MIT
