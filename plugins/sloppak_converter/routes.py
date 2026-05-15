"""In-app PSARC → sloppak converter (+ optional Demucs stem split).

Exposes a single-worker background job queue over REST + WebSocket:

    POST /api/plugins/sloppak_converter/enqueue        body: {filename, split}
    POST /api/plugins/sloppak_converter/enqueue_bulk   body: {filenames, split, reconvert}
    GET  /api/plugins/sloppak_converter/jobs
    GET  /api/plugins/sloppak_converter/missing_sloppak  (same filter querystring as /api/library)
    POST /api/plugins/sloppak_converter/cancel_queued
    POST /api/plugins/sloppak_converter/retry_failed
    POST /api/plugins/sloppak_converter/clear_finished
    DELETE /api/plugins/sloppak_converter/jobs/{job_id}
    WS   /ws/plugins/sloppak_converter/events

Conversion work happens in a thread pool (not the asyncio loop), streaming
progress back to every connected client via `loop.call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

# lib/ is already on sys.path via server.py, but be defensive for reload cases.
_LIB = Path(__file__).resolve().parents[2] / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from sloppak_convert import (  # noqa: E402
    convert_psarc_to_sloppak,
    split_sloppak_stems,
    demucs_available,
    sanitize_stem,
    _get_demucs_server_url as _demucs_server_url,
)


def _split_available() -> bool:
    """Stem splitting can run if either local demucs is importable
    or a remote demucs server is configured. Centralized so the
    job-queue gate and the module-load status log stay in sync."""
    return demucs_available() or _demucs_server_url() is not None


def _cleanup_stale_torchcodec() -> None:
    """Remove leftover torchcodec install from prior plugin versions.

    pip install --target is additive, so dropping torchcodec from
    requirements.txt does not delete the on-disk install. Recent torchaudio
    routes torchaudio.save through save_with_torchcodec, which loads
    torchcodec; on Windows desktop the bundled vgmstream-patched FFmpeg DLLs
    on PATH break torchcodec's symbol resolution and the demucs subprocess
    crashes with OSError. The core repo's bootstrap shim sidesteps the
    .save path; this hook removes the stale install so other torchaudio
    code paths cannot accidentally probe it. Idempotent: no-op when nothing
    to remove.
    """
    config_dir = os.environ.get("CONFIG_DIR")
    if not config_dir:
        appdata = os.environ.get("APPDATA")
        if appdata:
            # Windows desktop bundle.
            config_dir = str(Path(appdata) / "slopsmith-desktop" / "slopsmith-config")
        elif Path("/config").is_dir():
            # Linux Docker convention: Slopsmith config is mounted at /config.
            config_dir = "/config"
        else:
            # Last-resort Windows fallback for the case where APPDATA is
            # unset (rare; e.g. service contexts). Linux installs without
            # CONFIG_DIR or /config land here too — the `is_dir()` guard
            # below makes the hook a safe no-op.
            config_dir = str(Path.home() / "AppData" / "Roaming"
                             / "slopsmith-desktop" / "slopsmith-config")
    pkgs = Path(config_dir) / "pip_packages"
    if not pkgs.is_dir():
        return
    removed = []
    failed = []
    for pattern in ("torchcodec", "torchcodec-*.dist-info"):
        for p in pkgs.glob(pattern):
            try:
                shutil.rmtree(p)
            except OSError as e:
                # Best-effort: log so the user has an actionable signal if a
                # stale install survives (file lock, permissions). Don't raise
                # — failing to clean up should not block the rest of plugin
                # init, since the core bootstrap shim makes the .save path
                # work regardless.
                print(f"[sloppak_converter] failed to remove {p}: {e}")
            if p.exists():
                failed.append(p.name)
            else:
                removed.append(p.name)
    if removed:
        print(f"[sloppak_converter] removed stale torchcodec install: {', '.join(removed)}")
    if failed:
        print(f"[sloppak_converter] WARNING: stale torchcodec paths still present after cleanup: {', '.join(failed)}. "
              f"Remove manually from {pkgs} if Demucs splits start failing.")


_cleanup_stale_torchcodec()


# ── Check demucs availability at module load ─────────────────────────────────

if not demucs_available():
    _server_url = _demucs_server_url()
    if _server_url:
        print(f"[sloppak_converter] Local demucs not available — using configured server ({_server_url})")
    else:
        print("[sloppak_converter] Local demucs not available — stem splitting will be skipped. Configure a demucs server in Settings for stem support.")


# ── Helpers shared across enqueue paths ──────────────────────────────────────

def _stem_for_psarc(psarc_filename: str) -> str:
    """Sanitized stem used for the output `.sloppak` filename — mirrors the
    convention in `_run_job_sync` so the disk-existence check sees the same
    target the worker would produce."""
    p = Path(psarc_filename)
    return sanitize_stem(p.stem.replace("_p", "").replace("_m", ""))


def _meta_for(filename: str) -> dict:
    """Pull display metadata (title/artist/album/duration/tuning/arrangements)
    out of the shared `meta_db` for one PSARC. Returns an empty dict if the
    DB or the row is missing — callers tolerate absent fields."""
    meta_db = _context.get("meta_db")
    if meta_db is None or not filename:
        return {}
    try:
        row = meta_db.conn.execute(
            "SELECT title, artist, album, duration, tuning_name, arrangements "
            "FROM songs WHERE filename = ?", (filename,)
        ).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    arrangements: list = []
    try:
        if row[5]:
            arrangements = json.loads(row[5]) or []
    except Exception:
        arrangements = []
    return {
        "title": row[0] or "",
        "artist": row[1] or "",
        "album": row[2] or "",
        "duration": float(row[3] or 0),
        "tuning_name": row[4] or "",
        "arrangements": arrangements,
    }


def _sloppak_already_exists(dlc_root: Path, psarc_filename: str) -> bool:
    """True iff a previously-converted `.sloppak` for this PSARC already
    sits at the canonical output path. Disk check is authoritative —
    `_jobs[].output_path` is wiped by `clear_finished` and lost across
    restarts, so a job-state lookup would miss legitimate previous work."""
    return (dlc_root / "sloppak" / f"{_stem_for_psarc(psarc_filename)}.sloppak").exists()


# ── Module state ──────────────────────────────────────────────────────────────

# Caps for `enqueue_bulk` input — defence against OOM / loop-blocking from
# pathological client input. 10k is well past any plausible real library;
# 4096 chars covers every sane filesystem path (FAT/NTFS/ext4/HFS limits).
_MAX_BULK_FILENAMES = 10000
_MAX_FILENAME_LEN = 4096

# {job_id: {...}}
_jobs: dict[str, dict] = {}
_queue: "asyncio.Queue[str]" = None  # type: ignore[assignment]
_ws_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None
_worker_task: asyncio.Task | None = None
_context: dict = {}
# Pause gate. `_resume_event.set()` = running, `.clear()` = paused. Worker
# waits on this AFTER pulling a job from the queue, so pause is observed
# the instant any in-flight job between dequeue and execution would start —
# but a job already in `run_in_executor` is allowed to finish (cancelling
# an in-progress conversion mid-Demucs is out of scope per issue #107).
_resume_event: asyncio.Event | None = None


def _now() -> float:
    return time.time()


# ── Job persistence ───────────────────────────────────────────────────────────
# Without this, every restart wipes the in-memory `_jobs` dict and any work the
# user queued (often hundreds of bulk-enqueued PSARCs) is silently dropped on
# the floor. Persist to a single JSON file under the host's config dir so a
# restart picks up exactly where we left off. Saves are triggered on state
# transitions / enqueue / removal only — not on progress ticks, which fire
# many times per second during Demucs and would thrash the disk.

_JOBS_FILENAME = "sloppak_converter_jobs.json"


def _jobs_file() -> Path | None:
    config_dir = _context.get("config_dir")
    if not config_dir:
        return None
    return Path(config_dir) / _JOBS_FILENAME


def _save_jobs() -> None:
    """Atomic write of `_jobs` to disk. No-op if no config_dir is wired
    (early bootstrap, exotic test harnesses). MUST be called from the
    event-loop thread: `_run_job_sync` runs in an executor and mutates
    job dicts (output_path, result_*) directly, so we snapshot each job
    on the caller's thread before handing the payload to `json.dump`.
    Without the snapshot, `json.dump` could see "dictionary changed size
    during iteration" or persist a partially-mutated job."""
    path = _jobs_file()
    if path is None:
        return
    try:
        # Shallow-copy each job dict on the loop thread to freeze the
        # keyset/values against concurrent worker-thread writes. Loop-
        # thread mutations of `_jobs` itself (add/remove/state changes)
        # are serialized with this caller by the GIL + single-threaded
        # async runtime. The result_* keys that `_run_job_sync` writes
        # are pre-initialized in `_enqueue_one`, so the worker never
        # adds new keys mid-snapshot — `dict(j)` only iterates a fixed
        # keyset whose values may change but whose size does not.
        # Snapshot construction is inside the try/except as defense in
        # depth: if a future code path violates that invariant the
        # exception is caught and logged, not bubbled up to the caller.
        snapshot = {"jobs": [dict(j) for j in list(_jobs.values())]}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(snapshot, f)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[sloppak_converter] failed to persist jobs: {e}")


def _is_safe_psarc_relpath(filename: str) -> bool:
    """Mirror the shape checks `_enqueue_one` / `_validate_and_load_meta_sync`
    apply at enqueue time. Used on persistence load so a hand-edited or
    corrupted jobs file can't sneak an absolute path / `..` traversal /
    non-PSARC filename past the worker, where it would be joined onto
    `dlc_root` and converted blindly.

    Pure-syntactic check — no disk lookup. If `dlc_root` later resolves
    the joined path outside its root (or the file is missing) the
    worker's own error handling already kicks in; this is just the
    first line of defence."""
    if not isinstance(filename, str) or not filename:
        return False
    if not filename.lower().endswith(".psarc"):
        return False
    try:
        p = Path(filename)
    except (TypeError, ValueError):
        return False
    if p.is_absolute():
        return False
    if any(part == ".." for part in p.parts):
        return False
    return True


def _load_jobs_from_disk() -> None:
    """Repopulate `_jobs` from the persisted JSON file. Called once during
    setup() before the worker queue is filled. Any job left in `running`
    state at shutdown is demoted to `queued` so the new worker picks it
    back up — the previous worker died mid-conversion and progress is
    not recoverable across processes.

    Idempotent: always clears `_jobs` first so re-running setup (test
    reloads, repeated lifespan starts, or the persistence file being
    deleted out from under us) reflects disk truth instead of leaving
    stale in-memory rows."""
    _jobs.clear()
    path = _jobs_file()
    if path is None or not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[sloppak_converter] failed to read persisted jobs at {path}: {e}")
        return
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return
    # Required fields + types. Downstream code (`_worker_loop`,
    # `_run_job_sync`, dedupe in `_enqueue_one`, the retry/cancel paths)
    # all index these directly with `job["filename"]` / `job["state"]`,
    # so a row missing them would KeyError mid-drain and stall the
    # worker. A corrupted or hand-edited persistence file should be
    # skipped row-by-row, not allowed to wedge the queue.
    _VALID_STATES = {"queued", "running", "done", "error", "cancelled"}
    # Keys that `_run_job_sync` mutates directly on the worker thread.
    # If a persisted row is missing any of these, the worker would
    # *add* the key on retry — re-introducing the concurrent-mutation
    # hazard the snapshot path in `_save_jobs()` is built to avoid.
    # Backfill them so the worker only ever mutates existing values.
    # Each entry is `(key, factory)` rather than `(key, value)` so
    # mutable defaults (the `result_stems` list) get a fresh instance
    # per job — a literal `[]` shared via `setdefault` would let any
    # in-place mutation on one job's list bleed into every other
    # backfilled job.
    _WORKER_MUTATED_DEFAULTS = (
        ("output_path", lambda: ""),
        ("demucs_skipped", lambda: False),
        ("result_stems", list),
        ("result_stem_count", lambda: 0),
        ("result_size", lambda: 0),
    )
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_id = job.get("id")
        filename = job.get("filename")
        state = job.get("state")
        if (not isinstance(job_id, str) or not job_id
                or not isinstance(filename, str) or not filename
                or state not in _VALID_STATES):
            print(f"[sloppak_converter] skipping malformed persisted job: "
                  f"id={job_id!r} filename={filename!r} state={state!r}")
            continue
        # Path-safety check matches enqueue-time validation so a
        # hand-edited or corrupted persistence file can't smuggle an
        # absolute path / `..` traversal / non-PSARC filename into the
        # worker, where it would be joined onto `dlc_root` blindly.
        if not _is_safe_psarc_relpath(filename):
            print(f"[sloppak_converter] skipping persisted job with unsafe "
                  f"filename: id={job_id!r} filename={filename!r}")
            continue
        # `split` is read as a bool by the worker; coerce defensively
        # rather than skip an otherwise-valid row.
        job["split"] = bool(job.get("split", False))
        # Fill in any worker-mutated keys missing from the persisted
        # row (older persistence files, hand-edited rows, or rows from
        # before result_* pre-init landed). Without this, retry of a
        # loaded job would have the worker thread *add* these keys
        # mid-conversion, racing concurrent `_save_jobs()` calls.
        for key, factory in _WORKER_MUTATED_DEFAULTS:
            if key not in job:
                job[key] = factory()
        if state == "running":
            # The worker that owned this job died with the previous
            # process. Reset transient run-state so the new worker
            # starts it cleanly from the top.
            job["state"] = "queued"
            job["progress"] = 0.0
            job["stage"] = "queued"
            job["message"] = ""
            job["started_at"] = None
        _jobs[job_id] = job


def _public_job(job: dict) -> dict:
    """Strip internal fields before pushing to clients."""
    return {k: v for k, v in job.items() if not k.startswith("_")}


async def _broadcast(event: dict) -> None:
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


def _schedule_broadcast(event: dict) -> None:
    """Thread-safe: enqueue a broadcast onto the event loop."""
    if _loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(_broadcast(event), _loop)
    except Exception:
        pass


def _update_job(job_id: str, **fields) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    new_state = fields.get("state")
    state_changed = "state" in fields and new_state != job.get("state")
    job.update(fields)
    # Only persist on terminal state transitions. `_make_progress_cb`
    # calls `_update_job`-equivalent paths many times a second during
    # Demucs and would thrash the disk if we persisted ticks. Transitions
    # *into* `running` are also skipped: `_load_jobs_from_disk()` demotes
    # any `running` row back to `queued` on restart anyway, so writing
    # the "running" delta costs an extra full-file rewrite per job and
    # buys nothing. The next save (done/error) captures everything.
    if state_changed and new_state != "running":
        _save_jobs()
    _schedule_broadcast({"type": "job_update", "job": _public_job(job)})


def _make_progress_cb(job_id: str):
    """Build a progress_cb closure for sloppak_convert. Called from worker thread."""
    def cb(fraction: float, stage: str, message: str) -> None:
        job = _jobs.get(job_id)
        if not job:
            return
        # Use call_soon_threadsafe to hop back to the loop for broadcast.
        if _loop is None:
            return
        def _apply():
            # Re-check that the job still exists. `clear_finished` may
            # have evicted it between the worker thread scheduling this
            # apply and the loop thread executing it; mutating + broad-
            # casting an evicted job would resurrect a zombie row in
            # connected dashboards until the next snapshot.
            if _jobs.get(job_id) is None:
                return
            job["progress"] = float(fraction)
            job["stage"] = stage
            job["message"] = message
            asyncio.create_task(_broadcast({"type": "job_update", "job": _public_job(job)}))
        _loop.call_soon_threadsafe(_apply)
    return cb


# ── Worker ────────────────────────────────────────────────────────────────────

def _run_job_sync(job: dict) -> None:
    """Synchronous body of one conversion job — runs in the thread pool."""
    filename = job["filename"]
    split = bool(job.get("split", False))

    get_dlc = _context.get("get_dlc_dir")
    dlc_raw = get_dlc() if callable(get_dlc) else None
    if not dlc_raw:
        raise RuntimeError("DLC folder is not configured")
    # Coerce to Path so callers passing str (e.g. test stubs, or future host
    # implementations) work the same as the canonical Path-returning shape.
    dlc_root: Path = Path(dlc_raw)

    psarc_path = dlc_root / filename
    if not psarc_path.exists():
        raise FileNotFoundError(f"source PSARC not found: {filename}")

    # Generated sloppaks live under DLC_DIR/sloppak/ to keep them separate.
    out_dir = dlc_root / "sloppak"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = sanitize_stem(psarc_path.stem.replace("_p", "").replace("_m", ""))
    out_path = out_dir / f"{stem}.sloppak"

    progress_cb = _make_progress_cb(job["id"])
    convert_psarc_to_sloppak(psarc_path, out_path, as_dir=False, progress_cb=progress_cb)

    if split:
        if not _split_available():
            progress_cb(0.9, "packing",
                        "Demucs not installed and no demucs server configured "
                        "— skipped stem split. Set Settings → Demucs Server "
                        "or install demucs locally to enable splitting.")
            job["demucs_skipped"] = True
        else:
            # Split takes up the second half of the progress bar conceptually,
            # but the CLI call is opaque so we just emit stage updates.
            def split_cb(f, s, m):
                # Remap 0..1 onto 0.5..1 so the bar keeps moving.
                progress_cb(0.5 + 0.5 * f, s, m)
            split_sloppak_stems(out_path, progress_cb=split_cb,
                                base_frac=0.0, span_frac=1.0)

    job["output_path"] = str(out_path)

    # Capture a small "what did Demucs produce" summary for the dashboard
    # so finished rows show stems + output size instead of just "done".
    # Failures here are non-fatal — the conversion already succeeded; the
    # dashboard just shows nothing extra.
    try:
        import sloppak as _sloppak_mod  # type: ignore
        meta = _sloppak_mod.extract_meta(out_path)
        job["result_stems"] = list(meta.get("stem_ids", []) or [])
        job["result_stem_count"] = int(meta.get("stem_count", 0) or 0)
    except Exception:
        pass
    try:
        job["result_size"] = out_path.stat().st_size
    except Exception:
        pass

    # Index the new sloppak in the host's metadata DB so it shows up in the
    # library immediately. Without this, the new file lands on disk but the
    # library only picks it up on the next periodic rescan (every 5 min) or
    # via a manual /api/rescan, leaving users to wonder where their
    # just-converted song went. Failures here are non-fatal — the conversion
    # itself already succeeded; the user can recover with a manual rescan.
    try:
        meta_db = _context.get("meta_db")
        extract_meta = _context.get("extract_meta")
        get_dlc_dir = _context.get("get_dlc_dir")
        if meta_db and extract_meta and get_dlc_dir and out_path.exists():
            dlc_dir = Path(get_dlc_dir())
            try:
                rel = out_path.relative_to(dlc_dir).as_posix()
            except ValueError:
                # out_path lives outside DLC root — fall back to bare name
                # (mirrors server.py:_rel behavior).
                rel = out_path.name
            st = out_path.stat()
            meta_db.put(rel, st.st_mtime, st.st_size, extract_meta(out_path))
    except Exception as e:
        print(f"[sloppak_converter] failed to index {out_path} in meta_db: {e}")


async def _worker_loop() -> None:
    while True:
        job_id = await _queue.get()
        # Block here while the queue is paused — but only AFTER we have
        # a job in hand, so the dequeue itself isn't blocked and the
        # client can still see new jobs land in `queued` state.
        if _resume_event is not None:
            await _resume_event.wait()
        job = _jobs.get(job_id)
        if not job:
            continue
        if job.get("state") == "cancelled":
            continue

        _update_job(job_id, state="running", started_at=_now(),
                    progress=0.0, stage="starting", message="")

        try:
            await asyncio.get_event_loop().run_in_executor(None, _run_job_sync, job)
            _update_job(job_id, state="done", progress=1.0, stage="done",
                        message="Conversion complete", finished_at=_now())
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[sloppak_converter] job {job_id} failed: {tb}")
            _update_job(job_id, state="error", stage="error",
                        message=str(e), finished_at=_now())


# ── FastAPI setup ─────────────────────────────────────────────────────────────

def setup(app: FastAPI, context: dict) -> None:
    global _queue, _loop, _worker_task, _context, _resume_event
    _context = context

    # Start worker immediately. Core's plugin loader marshals setup() back
    # onto the event-loop thread (server.py:_route_setup_on_main), so
    # `get_running_loop()` and `create_task` both work here. A late-
    # registered `@app.on_event("startup")` would NOT fire because app
    # startup has already completed by the time plugins are loaded.
    #
    # _queue and _resume_event are only (re)created when a new worker is
    # actually started.  Recreating them unconditionally would orphan the
    # existing worker: it would keep blocking on the old queue's `get()`
    # while new enqueues go to the new queue, silently stalling all jobs.
    #
    # Persisted-job rehydration is gated on the same fresh-worker
    # condition: `_load_jobs_from_disk()` clears `_jobs` and demotes
    # running→queued, so calling it while an existing worker still owns
    # the dict would clobber its in-flight state.
    def _fill_queue_from_jobs():
        """Re-enqueue jobs that are still marked 'queued' in _jobs but aren't
        yet in the new queue.  Called immediately after a fresh _queue is
        created (always asyncio.Queue()) so the queue is empty at that point —
        no duplicates are possible since each job_id appears at most once in
        the dict and the old queue has been replaced."""
        for job in _jobs.values():
            if job.get('state') == 'queued':
                _queue.put_nowait(job['id'])

    try:
        _loop = asyncio.get_running_loop()
        if _worker_task is None or _worker_task.done():
            _load_jobs_from_disk()
            _queue = asyncio.Queue()
            _resume_event = asyncio.Event()
            _resume_event.set()  # default = running
            _fill_queue_from_jobs()
            _worker_task = asyncio.create_task(_worker_loop())
            print("[sloppak_converter] worker started")
        else:
            print("[sloppak_converter] worker already running; skipping duplicate start")
    except RuntimeError:
        # No running event loop at setup time — happens when the plugin is
        # initialised synchronously (e.g. test fixtures, alternate embeddings).
        # Register a startup handler so the worker is created as soon as the
        # ASGI lifespan fires.  Guard both the queue re-creation and the handler
        # registration: if a worker is already running (e.g. the try branch ran
        # on a previous call), leave its queue intact so existing jobs keep
        # draining.
        if _worker_task is not None and not _worker_task.done():
            print("[sloppak_converter] worker already running; skipping synchronous re-setup")
        else:
            _load_jobs_from_disk()
            _queue = asyncio.Queue()
            _resume_event = asyncio.Event()
            _resume_event.set()  # default = running
            _fill_queue_from_jobs()
            print("[sloppak_converter] no running loop at setup; worker will start on app startup")

            @app.on_event("startup")
            async def _start_worker_on_startup():
                global _worker_task, _loop
                # Capture the event loop so _schedule_broadcast works after startup.
                _loop = asyncio.get_event_loop()
                if _worker_task is None or _worker_task.done():
                    if _worker_task is not None and _worker_task.done():
                        print("[sloppak_converter] previous worker task finished; restarting")
                    _worker_task = asyncio.create_task(_worker_loop())
                    print("[sloppak_converter] worker started (deferred startup)")

    def _validate_and_load_meta_sync(filename: str, dlc_root: Path,
                                      reconvert: bool) -> dict:
        """Sync portion of `_enqueue_one`: filename validation, path-
        traversal checks, disk existence, already-converted gate, and
        the meta_db lookup. Designed to be called via `asyncio.to_thread`
        so the loop isn't blocked when bulk-enqueueing thousands of
        filenames. Returns either `{skipped: True, reason}` or
        `{meta: dict}` on success."""
        try:
            p = Path(filename)
            if p.is_absolute() or any(part == ".." for part in p.parts):
                return {"skipped": True, "reason": "not_found"}
            candidate = (dlc_root / filename).resolve()
            dlc_resolved = dlc_root.resolve()
            candidate.relative_to(dlc_resolved)
        except (ValueError, OSError):
            return {"skipped": True, "reason": "not_found"}
        if not candidate.is_file():
            return {"skipped": True, "reason": "not_found"}
        if not reconvert and _sloppak_already_exists(dlc_root, filename):
            return {"skipped": True, "reason": "already_converted"}
        return {"meta": _meta_for(filename)}

    async def _enqueue_one(filename: str, split: bool, *, reconvert: bool = False,
                            dlc_root: Path | None = None) -> dict:
        """Shared enqueue body. Returns either `{ok, filename, job_id}` on
        success or `{skipped, filename, reason}` on skip. Validates filename
        shape, dedupes against in-progress jobs, optionally honors the
        already-converted skip. Bulk + single endpoints both go through this
        so the rules stay in lockstep.

        Sync I/O (path resolution, disk existence, sqlite metadata lookup)
        is offloaded to a worker thread so a 1000-PSARC bulk enqueue
        doesn't freeze the event loop / WS broadcasts. `_jobs` mutations
        and the queue.put still happen on the loop thread for safety."""
        if not filename:
            return {"skipped": True, "filename": filename, "reason": "not_found"}
        if not filename.lower().endswith(".psarc"):
            return {"skipped": True, "filename": filename, "reason": "not_psarc"}
        if dlc_root is None:
            get_dlc = _context.get("get_dlc_dir")
            dlc_root = get_dlc() if callable(get_dlc) else None
        if dlc_root is None:
            return {"skipped": True, "filename": filename, "reason": "not_found"}

        validated = await asyncio.to_thread(
            _validate_and_load_meta_sync, filename, dlc_root, reconvert
        )
        if validated.get("skipped"):
            return {"skipped": True, "filename": filename, "reason": validated["reason"]}

        # Dedup is intentionally read AFTER the off-thread validation so
        # that two concurrent bulk enqueues for the same filename can't
        # both pass the dedup check before either inserts. With the GIL
        # the for-loop + insert is effectively atomic from the loop
        # thread's perspective.
        for j in _jobs.values():
            if j["filename"] == filename and j["state"] == "queued":
                return {"skipped": True, "filename": filename, "reason": "already_queued",
                        "job_id": j["id"]}
            if j["filename"] == filename and j["state"] == "running":
                return {"skipped": True, "filename": filename, "reason": "already_running",
                        "job_id": j["id"]}

        job_id = uuid.uuid4().hex[:8]
        meta = validated["meta"]
        job = {
            "id": job_id,
            "filename": filename,
            "split": split,
            "state": "queued",
            "progress": 0.0,
            "stage": "queued",
            "message": "",
            "output_path": "",
            "demucs_skipped": False,
            # Pre-initialize the result_* keys so `_run_job_sync` only
            # mutates values, never adds new keys. The save-time snapshot
            # iterates each job dict, so a worker-thread `job["result_x"] = ...`
            # against a not-yet-present key could otherwise race against
            # a concurrent `dict(job)` on the loop thread.
            "result_stems": [],
            "result_stem_count": 0,
            "result_size": 0,
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "title": meta.get("title", ""),
            "artist": meta.get("artist", ""),
            "album": meta.get("album", ""),
            "duration": meta.get("duration", 0),
            "tuning_name": meta.get("tuning_name", ""),
            "arrangements": meta.get("arrangements", []),
        }
        _jobs[job_id] = job
        # Persistence is deferred to the caller (single / bulk / retry
        # endpoints) so a 1000-PSARC bulk enqueue writes the file once
        # instead of N times with O(N) bytes per write — the inner
        # write-amplification was O(N^2) total bytes.
        await _queue.put(job_id)
        await _broadcast({"type": "job_update", "job": _public_job(job)})
        return {"ok": True, "filename": filename, "job_id": job_id}

    @app.post("/api/plugins/sloppak_converter/enqueue")
    async def enqueue(data: dict):
        # Single-file enqueue. Preserves the existing wire shape that
        # screen.js's per-card / per-row buttons depend on, but routes
        # through `_enqueue_one` so the dedupe + already-converted rules
        # stay identical to the bulk path.
        filename = (data.get("filename") or "").strip()
        split = bool(data.get("split", True))
        reconvert = bool(data.get("reconvert", False))
        result = await _enqueue_one(filename, split, reconvert=reconvert)
        if "ok" in result:
            _save_jobs()
            return {"ok": True, "job_id": result["job_id"]}
        # Map the new `skipped/reason` shape back to the legacy
        # `{error, job_id?}` shape so existing clients don't have to
        # change.
        msg = {
            "not_found": "filename required" if not filename else "source PSARC not found",
            "not_psarc": "not a PSARC",
            "already_queued": "already queued",
            "already_running": "already queued",
            "already_converted": "sloppak already exists (pass reconvert=true to override)",
        }.get(result["reason"], result["reason"])
        out: dict = {"error": msg}
        if "job_id" in result:
            out["job_id"] = result["job_id"]
        return out

    @app.post("/api/plugins/sloppak_converter/enqueue_bulk")
    async def enqueue_bulk(data: dict):
        """Enqueue many PSARCs in one round-trip. Skips already-queued /
        already-running / already-converted / non-PSARC / not-found
        entries with structured `reason` codes the client can surface to
        the user.

        Body:
            { filenames: [str], split: bool=true, reconvert: bool=false }
        Response:
            { enqueued: [{filename, job_id}],
              skipped:  [{filename, reason, job_id?}] }
        """
        filenames = data.get("filenames") or []
        if not isinstance(filenames, list):
            raise HTTPException(status_code=422, detail="filenames must be a list of strings")
        # Cap the request size to keep a malicious / confused client from
        # OOMing the server with a single enormous bulk. The plugin is
        # ultimately bound by the host's library size; 10k jobs is well
        # past anything a real Rocksmith DLC collection produces.
        if len(filenames) > _MAX_BULK_FILENAMES:
            raise HTTPException(
                status_code=413,
                detail=f"too many filenames (max {_MAX_BULK_FILENAMES})",
            )
        # Dedupe within the request itself so a sloppy client doesn't
        # double-enqueue. Order preserved (first occurrence wins).
        # Per-name length cap mirrors typical filesystem limits and
        # keeps `Path()`/`.resolve()` from doing pathological work on
        # adversarial input.
        seen = set()
        unique: list[str] = []
        for f in filenames:
            if not isinstance(f, str):
                continue
            if len(f) > _MAX_FILENAME_LEN:
                continue
            f = f.strip()
            if not f or f in seen:
                continue
            seen.add(f)
            unique.append(f)

        split = bool(data.get("split", True))
        reconvert = bool(data.get("reconvert", False))
        get_dlc = _context.get("get_dlc_dir")
        dlc_root: Path | None = get_dlc() if callable(get_dlc) else None

        enqueued: list[dict] = []
        skipped: list[dict] = []
        for fn in unique:
            result = await _enqueue_one(fn, split, reconvert=reconvert, dlc_root=dlc_root)
            if "ok" in result:
                enqueued.append({"filename": result["filename"], "job_id": result["job_id"]})
            else:
                entry = {"filename": result["filename"], "reason": result["reason"]}
                if "job_id" in result:
                    entry["job_id"] = result["job_id"]
                skipped.append(entry)
        # Single flush at end of the bulk so we write the file once
        # instead of once per enqueued PSARC.
        if enqueued:
            _save_jobs()
        return {"enqueued": enqueued, "skipped": skipped}

    @app.get("/api/plugins/sloppak_converter/jobs")
    async def list_jobs():
        # async so iteration of `_jobs` happens on the event-loop thread —
        # otherwise Starlette would dispatch us to the threadpool while
        # async enqueue endpoints mutate `_jobs[job_id] = job` on the loop,
        # risking `RuntimeError: dictionary changed size during iteration`.
        # Same rationale as `pause_queue` (commit f4b5035).
        return {
            "jobs": [_public_job(j) for j in _jobs.values()],
            "demucs_available": demucs_available(),
            "paused": _resume_event is not None and not _resume_event.is_set(),
        }

    @app.post("/api/plugins/sloppak_converter/pause")
    async def pause_queue():
        """Stop consuming new jobs. The currently-running job (if any) is
        allowed to finish — interrupting an in-flight Demucs run is out of
        scope. Subsequent enqueues still queue normally; they wait for
        `/resume` to be processed.

        MUST be `async def` (not sync). Starlette runs sync endpoints in
        a threadpool; `asyncio.Event.clear()/.set()` called from a
        non-loop thread is not thread-safe — the worker awaiting
        `_resume_event.wait()` could fail to wake on resume, leaving one
        job orphaned in queued state while later enqueues drain past it
        (slopsmith-plugin-sloppak-converter#?)."""
        if _resume_event is None:
            return {"error": "not initialized"}
        _resume_event.clear()
        await _broadcast({"type": "queue_state", "paused": True})
        return {"ok": True, "paused": True}

    @app.post("/api/plugins/sloppak_converter/resume")
    async def resume_queue():
        """Resume queue processing. Worker picks up where it left off.
        See `pause_queue` for why this MUST be async."""
        if _resume_event is None:
            return {"error": "not initialized"}
        _resume_event.set()
        await _broadcast({"type": "queue_state", "paused": False})
        return {"ok": True, "paused": False}

    @app.delete("/api/plugins/sloppak_converter/jobs/{job_id}")
    async def cancel_job(job_id: str):
        # async so the read+write on `_jobs[job_id]` happens on the loop
        # thread — see `list_jobs` / `pause_queue` for the rationale.
        job = _jobs.get(job_id)
        if not job:
            return {"error": "not found"}
        if job["state"] == "queued":
            job["state"] = "cancelled"
            _save_jobs()
            await _broadcast({"type": "job_update", "job": _public_job(job)})
            return {"ok": True}
        return {"error": f"cannot cancel job in state {job['state']}"}

    @app.post("/api/plugins/sloppak_converter/cancel_queued")
    async def cancel_queued():
        """Bulk-cancel every job currently in `queued` state. Running jobs
        are intentionally untouched (cooperative cancel of a running
        Demucs run is out of scope; see issue #107).

        async so iteration / mutation of `_jobs` happens on the loop
        thread — see `list_jobs` for rationale."""
        n = 0
        for job in _jobs.values():
            if job["state"] == "queued":
                job["state"] = "cancelled"
                n += 1
        if n:
            _save_jobs()
            # Send one snapshot instead of a per-job broadcast to avoid a
            # burst of hundreds of events when cancelling a large queue.
            await _broadcast({
                "type": "snapshot",
                "jobs": [_public_job(j) for j in _jobs.values()],
                "demucs_available": demucs_available(),
                "paused": _resume_event is not None and not _resume_event.is_set(),
            })
        return {"cancelled": n}

    @app.post("/api/plugins/sloppak_converter/retry_failed")
    async def retry_failed():
        """Re-enqueue every job currently in `error` state as a fresh job
        (new id, fresh `created_at`). The old error jobs are preserved
        so the user can still inspect the failure messages — call
        `/clear_finished` to evict them when ready. Returns the same
        `enqueued` / `skipped` shape as `/enqueue_bulk` for symmetry."""
        # Snapshot first — we'll mutate `_jobs` as we go and don't want
        # to iterate a changing dict.
        # For each filename, pick the *most recent* failed job so that
        # retrying reflects the latest attempt's settings rather than the
        # oldest one still in the list.
        latest: dict[str, dict] = {}
        for job in _jobs.values():
            if job["state"] == "error":
                fn = job["filename"]
                job_ts = job.get("created_at") or 0
                if fn not in latest:
                    latest[fn] = job
                else:
                    latest_ts = latest[fn].get("created_at") or 0
                    if job_ts > latest_ts:
                        latest[fn] = job
        failed_jobs: list[tuple[str, bool]] = [
            (j["filename"], j.get("split", False)) for j in latest.values()
        ]
        get_dlc = _context.get("get_dlc_dir")
        dlc_root: Path | None = get_dlc() if callable(get_dlc) else None
        enqueued: list[dict] = []
        skipped: list[dict] = []
        for fn, split in failed_jobs:
            # Use reconvert=True so jobs that failed *after* the .sloppak
            # was written (e.g. during stem splitting) are not silently
            # skipped by the already_converted gate.
            result = await _enqueue_one(fn, split, reconvert=True, dlc_root=dlc_root)
            if "ok" in result:
                enqueued.append({"filename": result["filename"], "job_id": result["job_id"]})
            else:
                entry = {"filename": result["filename"], "reason": result["reason"]}
                if "job_id" in result:
                    entry["job_id"] = result["job_id"]
                skipped.append(entry)
        if enqueued:
            _save_jobs()
        return {"enqueued": enqueued, "skipped": skipped}

    @app.post("/api/plugins/sloppak_converter/clear_finished")
    async def clear_finished():
        """Evict `done | error | cancelled` jobs from `_jobs` so the
        dashboard doesn't grow unbounded across long-running sessions.
        `queued` and `running` are preserved. Broadcasts a fresh
        `snapshot` event so connected dashboards see the cleared state
        immediately without needing to reconnect or refetch.

        async so the iteration + popping happens on the loop thread —
        see `list_jobs` for rationale."""
        cleared = 0
        for job_id in list(_jobs.keys()):
            if _jobs[job_id]["state"] in ("done", "error", "cancelled"):
                _jobs.pop(job_id, None)
                cleared += 1
        if cleared:
            _save_jobs()
        await _broadcast({
            "type": "snapshot",
            "jobs": [_public_job(j) for j in _jobs.values()],
            "demucs_available": demucs_available(),
            "paused": _resume_event is not None and not _resume_event.is_set(),
        })
        return {"cleared": cleared}

    @app.get("/api/plugins/sloppak_converter/missing_sloppak")
    def missing_sloppak(request: Request):
        """Return the list of PSARC filenames in the library that don't
        have a paired sloppak yet. Accepts the same filter querystring
        as `/api/library` (`q`, `format`, `arrangements_has`, `tunings`,
        `favorites`, etc.) so "Convert all PSARCs missing a sloppak (in
        current view)" honors the user's active search/filters.

        Server-side because client-side would walk dozens of paginated
        `/api/library` pages; `meta_db` is already indexed and this is
        a single SQL pass.
        """
        meta_db = _context.get("meta_db")
        if meta_db is None:
            return {"filenames": [], "count": 0,
                    "error": "meta_db not available"}

        qp = request.query_params

        # Respect the user's format filter: if they've narrowed to a
        # non-PSARC format (e.g. sloppak), there are no PSARCs in the
        # current view so return an empty result immediately instead of
        # returning PSARCs that are not visible to the user.
        user_format = qp.get("format", "").strip()
        if user_format and user_format != "psarc":
            return {"filenames": [], "count": 0}

        # Pull the filter params out of the querystring and forward them
        # to `query_page` so the result honors the user's current view.
        # The `format` param has to be forced to 'psarc' since we're
        # asking specifically about PSARCs that lack a sloppak — passing
        # the user's format filter through would let `format=sloppak`
        # short-circuit to an empty result set.
        def _split_csv(v: str) -> list[str]:
            return [s.strip() for s in (v or "").split(",") if s.strip()]
        def _maybe_int(v: str | None):
            if v in ("0", "1"):
                return int(v)
            return None

        # Query all PSARCs matching the user's filters. We page in 100-
        # row batches (the per-call clamp imposed by query_page); full
        # library iteration is fine for this use case (one click).
        fav_raw = qp.get("favorites") or "0"
        favorites_only = fav_raw == "1"
        psarc_files: list[str] = []
        page = 0
        size = 100  # `query_page` clamps at 100
        while True:
            songs, total = meta_db.query_page(
                q=qp.get("q", ""),
                page=page,
                size=size,
                sort=qp.get("sort", "artist"),
                direction=qp.get("direction", "asc"),
                favorites_only=favorites_only,
                format_filter="psarc",
                arrangements_has=_split_csv(qp.get("arrangements_has", "")),
                arrangements_lacks=_split_csv(qp.get("arrangements_lacks", "")),
                stems_has=_split_csv(qp.get("stems_has", "")),
                stems_lacks=_split_csv(qp.get("stems_lacks", "")),
                has_lyrics=_maybe_int(qp.get("has_lyrics")),
                tunings=_split_csv(qp.get("tunings", "")),
            )
            psarc_files.extend(s["filename"] for s in songs)
            if (page + 1) * size >= total or not songs:
                break
            page += 1

        # Disk-existence check is the source of truth (matches the
        # `_sloppak_already_exists` helper used by the enqueue path), so
        # the result here agrees with what the bulk enqueue would
        # actually do.
        get_dlc = _context.get("get_dlc_dir")
        dlc_root: Path | None = get_dlc() if callable(get_dlc) else None
        if dlc_root is None:
            return {"filenames": [], "count": 0,
                    "error": "DLC folder not configured"}
        missing = [f for f in psarc_files if not _sloppak_already_exists(dlc_root, f)]
        return {"filenames": missing, "count": len(missing)}

    @app.websocket("/ws/plugins/sloppak_converter/events")
    async def events_ws(ws: WebSocket):
        await ws.accept()
        _ws_clients.add(ws)
        try:
            # Send current job snapshot on connect.
            await ws.send_json({
                "type": "snapshot",
                "jobs": [_public_job(j) for j in _jobs.values()],
                "demucs_available": demucs_available(),
                "paused": _resume_event is not None and not _resume_event.is_set(),
            })
            while True:
                # We don't expect messages from the client — just keep alive.
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            _ws_clients.discard(ws)
