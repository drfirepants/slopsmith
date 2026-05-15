"""Tests for the bulk + queue-management endpoints added in v0.3.0
(slopsmith#107).

Bypasses the real conversion pipeline by stubbing the heavy
`_run_job_sync` so jobs progress through their state machine without
spawning Demucs / extracting PSARCs.

The plugin's `routes.py` imports from the Slopsmith host's `lib/`
(e.g. `sloppak_convert`). Tests therefore need the host on
`sys.path` — they look for it via the `SLOPSMITH_ROOT` env var first,
then fall back to a `../slopsmith` sibling checkout. CI clones the
host alongside this repo and sets `SLOPSMITH_ROOT` accordingly.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Slopsmith host discovery ─────────────────────────────────────────────────
# routes.py imports from the host's `lib/`. We resolve the host once at
# module import time so individual tests stay focused on plugin behavior.

_PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _find_slopsmith_root() -> Path:
    env = os.environ.get("SLOPSMITH_ROOT")
    if env:
        p = Path(env).resolve()
        if (p / "lib" / "sloppak_convert.py").exists():
            return p
        raise RuntimeError(
            f"SLOPSMITH_ROOT={p} does not look like a Slopsmith checkout "
            f"(missing lib/sloppak_convert.py)."
        )
    # Sibling fallback for local dev: assume `../slopsmith/lib` exists.
    sibling = _PLUGIN_DIR.parent / "slopsmith"
    if (sibling / "lib" / "sloppak_convert.py").exists():
        return sibling
    raise RuntimeError(
        "Could not locate a Slopsmith host checkout. Set SLOPSMITH_ROOT to "
        "the repo root, or place a clone at ../slopsmith next to this plugin."
    )


_SLOPSMITH_ROOT = _find_slopsmith_root()
_HOST_LIB = _SLOPSMITH_ROOT / "lib"
if str(_HOST_LIB) not in sys.path:
    sys.path.insert(0, str(_HOST_LIB))


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def plugin_routes(monkeypatch):
    """Re-import `routes` so module-level state (`_jobs`, `_queue`) is
    fresh for each test. Stubs the `convert_psarc_to_sloppak` and
    `split_sloppak_stems` calls inside the plugin so tests don't run
    the real pipeline."""
    sys.path.insert(0, str(_PLUGIN_DIR))
    if "routes" in sys.modules:
        del sys.modules["routes"]
    import routes
    importlib.reload(routes)

    def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(routes, "convert_psarc_to_sloppak", _noop)
    monkeypatch.setattr(routes, "split_sloppak_stems", _noop)
    monkeypatch.setattr(routes, "demucs_available", lambda: True)

    # Replace the worker loop with a no-op so jobs sit in `queued`
    # state for tests to inspect without racing against background
    # execution. Tests that want to verify state transitions mutate
    # `_jobs[id]["state"]` directly.
    async def _quiet_worker():
        while True:
            await asyncio.sleep(3600)
    monkeypatch.setattr(routes, "_worker_loop", _quiet_worker)
    yield routes


def _build_app_with_dlc(routes_mod, dlc_dir: Path, *, meta_db=None):
    """Build a FastAPI app with the plugin mounted and a context that
    points at a real (test-controlled) DLC directory. `meta_db` only
    needs to expose the `query_page` method that `missing_sloppak`
    calls."""
    app = FastAPI()
    context = {
        "get_dlc_dir": lambda: dlc_dir,
        "meta_db": meta_db,
        "config_dir": dlc_dir,
    }
    routes_mod.setup(app, context)
    return app


def _seed_psarc(dlc: Path, name: str) -> str:
    """Drop an empty file with .psarc extension so the existence check
    in `_enqueue_one` passes. The conversion is stubbed so the file
    contents don't matter."""
    p = dlc / name
    p.write_bytes(b"\x00")
    return name


def _seed_sloppak(dlc: Path, psarc_name: str) -> Path:
    """Pre-create a sloppak at the canonical path the plugin would
    write to, so `_sloppak_already_exists` returns True for the
    matching PSARC."""
    out_dir = dlc / "sloppak"
    out_dir.mkdir(parents=True, exist_ok=True)
    from routes import _stem_for_psarc
    out = out_dir / f"{_stem_for_psarc(psarc_name)}.sloppak"
    out.write_bytes(b"\x00")
    return out


class _FakeMetaDB:
    """Minimal stand-in for `MetadataDB.query_page` — returns a
    canned set of song dicts so `missing_sloppak` can iterate them
    without standing up a real SQLite database."""

    def __init__(self, songs: list[dict]):
        self.songs = songs

    def query_page(self, **kwargs):
        fmt = kwargs.get("format_filter", "")
        favorites_only = kwargs.get("favorites_only", False)
        rows = [s for s in self.songs
                if (not fmt or s.get("format", "psarc") == fmt)
                and (not favorites_only or s.get("favorite"))]
        return rows, len(rows)


class _ConnMetaDB:
    """Stand-in meta_db that implements the `conn.execute` interface used by
    `_meta_for` in addition to `query_page`. Supports testing job metadata
    enrichment without a real SQLite database.

    ``rows`` maps filename → (title, artist, album, duration, tuning_name,
    arrangements_json_or_None).
    """

    class _Cursor:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    def __init__(self, rows: dict | None = None, songs: list[dict] | None = None):
        self._rows = rows or {}
        self._songs = songs or []
        self.conn = self

    def execute(self, sql: str, params):
        filename = params[0] if params else None
        return self._Cursor(self._rows.get(filename))

    def query_page(self, **kwargs):
        fmt = kwargs.get("format_filter", "")
        favorites_only = kwargs.get("favorites_only", False)
        rows = [s for s in self._songs
                if (not fmt or s.get("format", "psarc") == fmt)
                and (not favorites_only or s.get("favorite"))]
        return rows, len(rows)


# ── Bulk enqueue ─────────────────────────────────────────────────────────────


def test_enqueue_bulk_happy_path(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    files = [_seed_psarc(dlc, f"song{i}_p.psarc") for i in range(3)]
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": files, "split": False})
    data = r.json()
    assert len(data["enqueued"]) == 3
    assert data["skipped"] == []


def test_enqueue_bulk_dedup_within_request(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "a_p.psarc")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn, fn, fn], "split": False})
    data = r.json()
    assert len(data["enqueued"]) == 1


def test_enqueue_bulk_skips_existing_sloppak(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    _seed_sloppak(dlc, fn)
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False})
    data = r.json()
    assert data["enqueued"] == []
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["reason"] == "already_converted"


def test_enqueue_bulk_reconvert_overrides_skip(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    _seed_sloppak(dlc, fn)
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False, "reconvert": True})
    data = r.json()
    assert len(data["enqueued"]) == 1
    assert data["skipped"] == []


def test_enqueue_bulk_not_psarc_skipped(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    sp = "song.sloppak"
    (dlc / sp).write_bytes(b"\x00")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [sp], "split": False})
    data = r.json()
    assert data["skipped"] == [{"filename": sp, "reason": "not_psarc"}]


def test_enqueue_bulk_rejects_oversize_batch(plugin_routes, tmp_path):
    """Cap on number of filenames in one bulk request — DoS guard."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        # Use cap+1 so we exercise the boundary; per-name validity doesn't
        # matter because rejection happens before per-item processing.
        big = [f"x{i}_p.psarc" for i in range(plugin_routes._MAX_BULK_FILENAMES + 1)]
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": big, "split": False})
    assert r.status_code == 413


def test_enqueue_bulk_skips_oversize_filename(plugin_routes, tmp_path):
    """Per-name length cap — silently skipped (not a hard rejection)
    so a single bad name in a batch doesn't kill the whole request."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    good = _seed_psarc(dlc, "ok_p.psarc")
    huge = "x" * (plugin_routes._MAX_FILENAME_LEN + 1) + "_p.psarc"
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [huge, good], "split": False})
    data = r.json()
    assert len(data["enqueued"]) == 1
    assert data["enqueued"][0]["filename"] == good


def test_enqueue_bulk_not_found(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": ["does_not_exist_p.psarc"], "split": False})
    data = r.json()
    assert data["skipped"][0]["reason"] == "not_found"


# ── Single-enqueue back-compat ───────────────────────────────────────────────


def test_single_enqueue_still_returns_legacy_shape(plugin_routes, tmp_path):
    """The pre-existing per-card buttons in screen.js depend on the
    `{ok, job_id}` / `{error, ...}` response shape — make sure
    routing through `_enqueue_one` preserves it."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue",
                        json={"filename": fn, "split": False})
    data = r.json()
    assert data.get("ok") is True
    assert "job_id" in data


def test_single_enqueue_legacy_error_shape_for_missing_file(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue",
                        json={"filename": "missing_p.psarc", "split": False})
    data = r.json()
    assert "error" in data


# ── Cancel-all-queued ────────────────────────────────────────────────────────


def test_cancel_queued_marks_all_cancelled(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    files = [_seed_psarc(dlc, f"s{i}_p.psarc") for i in range(3)]
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                    json={"filenames": files, "split": False})
        for j in plugin_routes._jobs.values():
            j["state"] = "queued"
        r = client.post("/api/plugins/sloppak_converter/cancel_queued")
    assert r.json()["cancelled"] == 3
    assert all(j["state"] == "cancelled" for j in plugin_routes._jobs.values())


# ── Retry-failed ─────────────────────────────────────────────────────────────


def test_retry_failed_creates_new_job_id(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "fail_p.psarc")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                    json={"filenames": [fn], "split": False})
        original_id = next(iter(plugin_routes._jobs))
        plugin_routes._jobs[original_id]["state"] = "error"
        r = client.post("/api/plugins/sloppak_converter/retry_failed")
    data = r.json()
    assert len(data["enqueued"]) == 1
    new_id = data["enqueued"][0]["job_id"]
    assert new_id != original_id
    assert original_id in plugin_routes._jobs
    assert plugin_routes._jobs[original_id]["state"] == "error"


# ── Clear-finished ───────────────────────────────────────────────────────────


def test_clear_finished_removes_terminal_states_only(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    files = [_seed_psarc(dlc, f"s{i}_p.psarc") for i in range(4)]
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                    json={"filenames": files, "split": False})
        states = ["queued", "running", "done", "error"]
        for job, state in zip(plugin_routes._jobs.values(), states):
            job["state"] = state
        r = client.post("/api/plugins/sloppak_converter/clear_finished")
    data = r.json()
    assert data["cleared"] == 2  # done + error
    remaining_states = {j["state"] for j in plugin_routes._jobs.values()}
    assert remaining_states <= {"queued", "running"}


# ── missing_sloppak ──────────────────────────────────────────────────────────


def test_missing_sloppak_returns_only_unpaired_psarcs(plugin_routes, tmp_path):
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    paired = _seed_psarc(dlc, "paired_p.psarc")
    _seed_sloppak(dlc, paired)
    unpaired1 = _seed_psarc(dlc, "alone1_p.psarc")
    unpaired2 = _seed_psarc(dlc, "alone2_p.psarc")
    fake_db = _FakeMetaDB([
        {"filename": paired, "format": "psarc"},
        {"filename": unpaired1, "format": "psarc"},
        {"filename": unpaired2, "format": "psarc"},
    ])
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=fake_db)
    client = TestClient(app)
    with client:
        r = client.get("/api/plugins/sloppak_converter/missing_sloppak")
    data = r.json()
    assert set(data["filenames"]) == {unpaired1, unpaired2}
    assert data["count"] == 2


def test_missing_sloppak_honors_favorites_filter(plugin_routes, tmp_path):
    """`?favorites=1` passthrough: only favorited PSARCs lacking
    sloppaks should come back."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fav = _seed_psarc(dlc, "fav_p.psarc")
    other = _seed_psarc(dlc, "other_p.psarc")
    fake_db = _FakeMetaDB([
        {"filename": fav, "format": "psarc", "favorite": True},
        {"filename": other, "format": "psarc", "favorite": False},
    ])
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=fake_db)
    client = TestClient(app)
    with client:
        r = client.get("/api/plugins/sloppak_converter/missing_sloppak?favorites=1")
    data = r.json()
    assert data["filenames"] == [fav]


def test_missing_sloppak_sloppak_format_returns_empty(plugin_routes, tmp_path):
    """When format=sloppak is specified, only sloppak files are visible,
    so PSARC files should not be returned as missing conversions."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    fake_db = _FakeMetaDB([{"filename": fn, "format": "psarc"}])
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=fake_db)
    client = TestClient(app)
    with client:
        r = client.get("/api/plugins/sloppak_converter/missing_sloppak?format=sloppak")
    data = r.json()
    assert data["filenames"] == []
    assert data["count"] == 0


# ── Path traversal guard ──────────────────────────────────────────────────────


def test_enqueue_bulk_path_traversal_rejected(plugin_routes, tmp_path):
    """A filename like `../outside.psarc` that resolves outside `dlc_root`
    must be rejected as `not_found` regardless of whether the target file
    exists on disk."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    # Create a real PSARC outside the DLC directory so the existence check
    # would pass if the path were not sanitised.
    outside = tmp_path / "outside_p.psarc"
    outside.write_bytes(b"\x00")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": ["../outside_p.psarc"], "split": False})
    data = r.json()
    assert data["skipped"][0]["reason"] == "not_found"


# ── Pause / Resume ────────────────────────────────────────────────────────────


def test_pause_returns_paused_state(plugin_routes, tmp_path):
    """POST /pause should report paused=True and the internal event
    should be cleared (not set)."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/pause")
    data = r.json()
    assert data.get("paused") is True
    # The resume event must be cleared so the worker gate blocks.
    assert not plugin_routes._resume_event.is_set()


def test_resume_after_pause_restores_running_state(plugin_routes, tmp_path):
    """POST /resume after a /pause should set the event again."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        client.post("/api/plugins/sloppak_converter/pause")
        assert not plugin_routes._resume_event.is_set()
        r = client.post("/api/plugins/sloppak_converter/resume")
    data = r.json()
    assert data.get("paused") is False
    assert plugin_routes._resume_event.is_set()


def test_paused_queue_stays_queued(plugin_routes, tmp_path):
    """Jobs enqueued while paused must remain in `queued` state (the
    quiet-worker stub is already in place; this test verifies the
    pause API doesn't break enqueueing itself)."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        client.post("/api/plugins/sloppak_converter/pause")
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False})
    data = r.json()
    assert len(data["enqueued"]) == 1
    job_id = data["enqueued"][0]["job_id"]
    # The job was accepted but should still be in queued state (worker
    # is paused and the test stub never processes it).
    assert plugin_routes._jobs[job_id]["state"] == "queued"


def test_retry_failed_uses_most_recent_settings(plugin_routes, tmp_path):
    """When a file has been failed twice with different `split` values,
    `retry_failed` must use the settings from the most recent failure."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        # First (older) failure: split=True
        client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                    json={"filenames": [fn], "split": True})
        first_id = next(iter(plugin_routes._jobs))
        plugin_routes._jobs[first_id]["state"] = "error"
        plugin_routes._jobs[first_id]["created_at"] = 1000

        # Second (newer) failure: split=False
        client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                    json={"filenames": [fn], "split": False, "reconvert": True})
        remaining_ids = set(plugin_routes._jobs.keys()) - {first_id}
        assert len(remaining_ids) == 1, (
            f"Expected exactly one new job after second enqueue, found {len(remaining_ids)}"
        )
        second_id = remaining_ids.pop()
        plugin_routes._jobs[second_id]["state"] = "error"
        plugin_routes._jobs[second_id]["created_at"] = 2000

        r = client.post("/api/plugins/sloppak_converter/retry_failed")
    data = r.json()
    assert len(data["enqueued"]) == 1
    new_id = data["enqueued"][0]["job_id"]
    # The retry job must carry the most recent settings (split=False).
    assert plugin_routes._jobs[new_id]["split"] is False


# ── Worker startup ─────────────────────────────────────────────────────────────


def test_setup_starts_worker_in_running_loop(plugin_routes, tmp_path):
    """setup() must schedule _worker_task when called from within a running
    event loop — the production path where the plugin loader marshals
    setup() onto the event-loop thread via server.py:_route_setup_on_main.

    The existing suite calls setup() *before* entering TestClient, so
    ``asyncio.get_running_loop()`` raises RuntimeError and the worker is
    never started there. This test covers the success branch explicitly.
    """
    dlc = tmp_path / "dlc"
    dlc.mkdir()

    async def _run():
        app = FastAPI()
        context = {
            "get_dlc_dir": lambda: dlc,
            "config_dir": dlc,
        }
        plugin_routes.setup(app, context)
        task = plugin_routes._worker_task
        assert task is not None, (
            "_worker_task must be set after setup() inside a running event loop"
        )
        # Yield to the event loop so the coroutine has a chance to start.
        await asyncio.sleep(0)
        assert not task.done(), "worker task must not have exited immediately after setup()"
        # Clean up: cancel the quiet-worker task created by setup().
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())


def test_enqueue_bulk_directory_rejected(plugin_routes, tmp_path):
    """A directory named *.psarc inside the DLC tree must be rejected by
    _enqueue_one — only regular files are valid inputs."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    # Create a directory with a .psarc name (not a regular file).
    dir_psarc = dlc / "notafile_p.psarc"
    dir_psarc.mkdir()
    app = _build_app_with_dlc(plugin_routes, dlc)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": ["notafile_p.psarc"], "split": False})
    data = r.json()
    assert data["enqueued"] == []
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["reason"] == "not_found"


def test_missing_sloppak_invalid_favorites_param(plugin_routes, tmp_path):
    """A non-numeric `favorites` query param (e.g. favorites=true) must
    not crash the endpoint with a 500 — it should be treated as falsy."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    db = _FakeMetaDB([{"filename": "song_p.psarc", "format": "psarc"}])
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=db)
    client = TestClient(app)
    with client:
        r = client.get("/api/plugins/sloppak_converter/missing_sloppak",
                       params={"favorites": "true"})
    # Must not 500 — a non-numeric value is silently treated as False.
    assert r.status_code == 200


# ── _meta_for enrichment ──────────────────────────────────────────────────────


def test_enqueue_enriches_job_with_metadata(plugin_routes, tmp_path):
    """When meta_db has a matching row, the job dict must include
    title/artist/album/duration/tuning_name/arrangements populated from
    the database rather than empty defaults."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "artist_song_p.psarc")
    meta_db = _ConnMetaDB(rows={
        fn: ("Song Title", "Artist Name", "Best Album", 182.5, "Eb Standard",
             '["lead", "rhythm"]'),
    })
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=meta_db)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False})
    job_id = r.json()["enqueued"][0]["job_id"]
    job = plugin_routes._jobs[job_id]
    assert job["title"] == "Song Title"
    assert job["artist"] == "Artist Name"
    assert job["album"] == "Best Album"
    assert job["duration"] == 182.5
    assert job["tuning_name"] == "Eb Standard"
    assert job["arrangements"] == ["lead", "rhythm"]


def test_enqueue_enriches_job_empty_when_no_row(plugin_routes, tmp_path):
    """If the file is not in meta_db the job fields must fall back to
    empty defaults — the worker must not crash on a missing row."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "unknown_p.psarc")
    meta_db = _ConnMetaDB(rows={})  # no entry for fn
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=meta_db)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False})
    job_id = r.json()["enqueued"][0]["job_id"]
    job = plugin_routes._jobs[job_id]
    assert job["title"] == ""
    assert job["artist"] == ""
    assert job["arrangements"] == []


def test_enqueue_enriches_job_tolerates_bad_arrangements_json(plugin_routes, tmp_path):
    """Malformed arrangements JSON must degrade gracefully to an empty
    list rather than raising an exception that blocks enqueueing."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "bad_p.psarc")
    meta_db = _ConnMetaDB(rows={
        fn: ("T", "A", "", 0, "", "not-valid-json"),
    })
    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=meta_db)
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False})
    job_id = r.json()["enqueued"][0]["job_id"]
    assert job_id in plugin_routes._jobs
    assert plugin_routes._jobs[job_id]["arrangements"] == []


def test_enqueue_enriches_job_tolerates_conn_exception(plugin_routes, tmp_path):
    """If meta_db.conn.execute raises, `_meta_for` must return an empty
    dict and the job must still be enqueued with empty metadata fields."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "err_p.psarc")

    class _BrokenDB:
        class _BrokenConn:
            def execute(self, *a, **k):
                raise RuntimeError("DB failure")
        conn = _BrokenConn()

        def query_page(self, **kwargs):
            return [], 0

    app = _build_app_with_dlc(plugin_routes, dlc, meta_db=_BrokenDB())
    client = TestClient(app)
    with client:
        r = client.post("/api/plugins/sloppak_converter/enqueue_bulk",
                        json={"filenames": [fn], "split": False})
    data = r.json()
    assert len(data["enqueued"]) == 1
    job = plugin_routes._jobs[data["enqueued"][0]["job_id"]]
    assert job["title"] == ""
    assert job["artist"] == ""


def test_setup_deferred_worker_starts_on_lifespan(plugin_routes, tmp_path):
    """When setup() is called synchronously (no running event loop) the
    worker must be started via the deferred startup handler so that jobs
    are actually drained after the ASGI lifespan fires."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    # Reset module state so setup() is called fresh without a running loop.
    plugin_routes._worker_task = None
    app = _build_app_with_dlc(plugin_routes, dlc)
    # TestClient enters the ASGI lifespan which fires the startup handler.
    with TestClient(app):
        assert plugin_routes._worker_task is not None, (
            "_worker_task must be set after the ASGI startup handler fires"
        )


def test_setup_repopulates_queue_with_existing_queued_jobs(plugin_routes, tmp_path):
    """When setup() creates a fresh _queue (e.g. on worker restart), any
    jobs already in _jobs with state='queued' must be re-enqueued so they
    are not silently stranded when the new worker starts draining."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()

    # Pre-write the persisted jobs file so setup() rehydrates it. (In-memory
    # pre-seeding no longer works because _load_jobs_from_disk clears _jobs
    # first to honor its idempotency contract — the previous in-memory
    # pattern was implicitly relying on module state surviving a "restart"
    # in the same process, which the disk-backed flow deliberately doesn't.)
    (dlc / "sloppak_converter_jobs.json").write_text(json.dumps({
        "jobs": [{
            "id": "pre-existing-id",
            "filename": "song_p.psarc",
            "state": "queued",
            "split": False,
        }]
    }))

    async def _run():
        app = FastAPI()
        context = {"get_dlc_dir": lambda: dlc, "config_dir": dlc}
        # Force worker_task to None so setup() creates a fresh queue.
        plugin_routes._worker_task = None
        plugin_routes.setup(app, context)

        assert plugin_routes._queue is not None, "_queue must be created by setup()"
        assert not plugin_routes._queue.empty(), (
            "pre-existing queued job must be placed in the new _queue"
        )
        job_id = plugin_routes._queue.get_nowait()
        assert job_id == "pre-existing-id", (
            "the re-enqueued item must match the stranded job's id"
        )

        # Clean up worker task.
        task = plugin_routes._worker_task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(_run())


# ── meta_db indexing on conversion done ──────────────────────────────────────


def _make_touching_convert(monkeypatch, plugin_routes):
    """Patch convert_psarc_to_sloppak so it creates out_path on disk,
    simulating a real conversion without running the actual pipeline."""
    def _touching(_psarc_path, out_path, **kwargs):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x00" * 32)
    monkeypatch.setattr(plugin_routes, "convert_psarc_to_sloppak", _touching)


def test_run_job_sync_calls_meta_db_put_with_correct_args(
    plugin_routes, monkeypatch, tmp_path
):
    """_run_job_sync must call meta_db.put() once after a successful
    conversion, passing the relative path, mtime, size, and the dict
    returned by extract_meta."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "artist_song_p.psarc")
    _make_touching_convert(monkeypatch, plugin_routes)

    put_calls = []

    class _TrackingMetaDB:
        def put(self, rel, mtime, size, meta):
            put_calls.append({"rel": rel, "mtime": mtime, "size": size, "meta": meta})

    fake_meta = {"title": "Test Song", "stem_ids": [], "stem_count": 0}

    def _fake_extract_meta(path):
        return fake_meta

    plugin_routes._context = {
        "get_dlc_dir": lambda: str(dlc),
        "meta_db": _TrackingMetaDB(),
        "extract_meta": _fake_extract_meta,
        "config_dir": dlc,
    }

    expected_stem = plugin_routes._stem_for_psarc(fn)
    job = {"id": "test-job-1", "filename": fn, "split": False}
    plugin_routes._run_job_sync(job)

    assert len(put_calls) == 1, "meta_db.put must be called exactly once"
    call = put_calls[0]
    assert call["rel"] == f"sloppak/{expected_stem}.sloppak"
    assert call["mtime"] > 0
    assert call["size"] == 32
    assert call["meta"] is fake_meta


def test_run_job_sync_meta_db_put_failure_does_not_raise(
    plugin_routes, monkeypatch, tmp_path
):
    """A meta_db.put() error must not propagate — conversion already
    succeeded, users can recover via a manual rescan."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song_p.psarc")
    _make_touching_convert(monkeypatch, plugin_routes)

    class _BrokenPutDB:
        def put(self, *args, **kwargs):
            raise RuntimeError("DB write failure")

    plugin_routes._context = {
        "get_dlc_dir": lambda: str(dlc),
        "meta_db": _BrokenPutDB(),
        "extract_meta": lambda path: {},
        "config_dir": dlc,
    }

    job = {"id": "test-job-2", "filename": fn, "split": False}
    # Must not raise even though put() raises.
    plugin_routes._run_job_sync(job)
    assert job.get("output_path") is not None


def test_run_job_sync_skips_indexing_when_no_extract_meta(
    plugin_routes, monkeypatch, tmp_path
):
    """When extract_meta is absent from context the indexing step must
    be silently skipped — no AttributeError, no stray put() call."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "nosplit_p.psarc")
    _make_touching_convert(monkeypatch, plugin_routes)

    put_calls = []

    class _TrackingMetaDB:
        def put(self, *args, **kwargs):
            put_calls.append(args)

    plugin_routes._context = {
        "get_dlc_dir": lambda: str(dlc),
        "meta_db": _TrackingMetaDB(),
        # extract_meta intentionally absent
        "config_dir": dlc,
    }

    job = {"id": "test-job-3", "filename": fn, "split": False}
    plugin_routes._run_job_sync(job)

    assert put_calls == [], "put must not be called when extract_meta is missing"


def test_run_job_sync_uses_basename_fallback_when_outside_dlc_root(
    plugin_routes, monkeypatch, tmp_path
):
    """When out_path cannot be made relative to the DLC root, meta_db.put
    must be called with just the basename (mirrors server.py:_rel)."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "outside_p.psarc")
    _make_touching_convert(monkeypatch, plugin_routes)

    put_calls = []

    class _TrackingMetaDB:
        def put(self, rel, mtime, size, meta):
            put_calls.append(rel)

    # Return the real DLC dir on the first call (so psarc_path and out_path
    # are computed correctly), then a completely different path on subsequent
    # calls so that out_path.relative_to(dlc_dir) raises ValueError and
    # triggers the basename fallback.
    call_count = [0]

    def _shifting_dlc_dir():
        call_count[0] += 1
        if call_count[0] == 1:
            return str(dlc)
        return str(tmp_path / "completely_different_root")

    plugin_routes._context = {
        "get_dlc_dir": _shifting_dlc_dir,
        "meta_db": _TrackingMetaDB(),
        "extract_meta": lambda path: {},
        "config_dir": dlc,
    }

    stem = plugin_routes._stem_for_psarc(fn)
    expected_basename = f"{stem}.sloppak"

    job = {"id": "test-job-4", "filename": fn, "split": False}
    plugin_routes._run_job_sync(job)

    assert len(put_calls) == 1, "put must be called once even for out-of-root paths"
    assert put_calls[0] == expected_basename


# ── Persistence across restart (issue #20) ───────────────────────────────────


def _reload_routes_module():
    """Drop the routes module from sys.modules and re-import it so module-
    level state (`_jobs`, `_queue`) is wiped. Used to simulate a fresh
    server process picking up the persisted jobs file."""
    if "routes" in sys.modules:
        del sys.modules["routes"]
    import routes
    importlib.reload(routes)

    async def _quiet_worker():
        while True:
            await asyncio.sleep(3600)
    routes._worker_loop = _quiet_worker
    return routes


def test_queued_jobs_persist_across_restart(plugin_routes, tmp_path):
    """A queued job written to disk before "shutdown" must come back as a
    queued job after a fresh setup() with the same config_dir."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song1_p.psarc")

    app1 = _build_app_with_dlc(plugin_routes, dlc)
    client1 = TestClient(app1)
    with client1:
        r = client1.post("/api/plugins/sloppak_converter/enqueue",
                         json={"filename": fn, "split": False})
        assert r.json().get("ok") is True
        first_id = r.json()["job_id"]

    jobs_file = dlc / "sloppak_converter_jobs.json"
    assert jobs_file.exists(), "persistence file should be written on enqueue"

    # Simulate restart: drop module state, re-import, run setup() again.
    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    client2 = TestClient(app2)
    with client2:
        r = client2.get("/api/plugins/sloppak_converter/jobs")
    jobs = r.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["id"] == first_id
    assert jobs[0]["state"] == "queued"
    assert jobs[0]["filename"] == fn


def test_running_jobs_demoted_to_queued_on_restart(plugin_routes, tmp_path):
    """A job that was mid-conversion when the server died must come back
    as queued (not running) so the new worker picks it up cleanly."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    _seed_psarc(dlc, "song1_p.psarc")

    # Hand-write a persisted-jobs file with one running job and one cancelled.
    jobs_file = dlc / "sloppak_converter_jobs.json"
    jobs_file.write_text(json.dumps({
        "jobs": [
            {
                "id": "running-1",
                "filename": "song1_p.psarc",
                "split": False,
                "state": "running",
                "progress": 0.42,
                "stage": "splitting",
                "message": "demucs in progress",
                "started_at": 1234.0,
            },
            {
                "id": "cancelled-1",
                "filename": "song1_p.psarc",
                "split": False,
                "state": "cancelled",
                "progress": 0.0,
                "stage": "queued",
                "message": "",
            },
        ]
    }))

    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    client2 = TestClient(app2)
    with client2:
        r = client2.get("/api/plugins/sloppak_converter/jobs")
    by_id = {j["id"]: j for j in r.json()["jobs"]}
    assert by_id["running-1"]["state"] == "queued"
    assert by_id["running-1"]["progress"] == 0.0
    assert by_id["running-1"]["stage"] == "queued"
    assert by_id["running-1"]["started_at"] is None
    # Non-running terminal states are preserved verbatim.
    assert by_id["cancelled-1"]["state"] == "cancelled"


def test_malformed_persisted_jobs_are_skipped(plugin_routes, tmp_path):
    """A corrupted or hand-edited persistence file with rows missing
    required fields (filename, state, id) must not stall the queue.
    Valid rows alongside invalid ones still load."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    (dlc / "sloppak_converter_jobs.json").write_text(json.dumps({
        "jobs": [
            {"id": "good-1", "filename": "ok.psarc", "state": "queued", "split": False},
            {"id": "no-filename", "state": "queued"},
            {"id": "bad-state", "filename": "x.psarc", "state": "garbage"},
            {"filename": "no-id.psarc", "state": "queued"},
            "not-a-dict",
            {"id": "good-2", "filename": "ok2.psarc", "state": "done"},
        ]
    }))

    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    client2 = TestClient(app2)
    with client2:
        r = client2.get("/api/plugins/sloppak_converter/jobs")
    jobs = r.json()["jobs"]
    ids = sorted(j["id"] for j in jobs)
    assert ids == ["good-1", "good-2"]


def test_load_fills_worker_mutated_key_defaults(plugin_routes, tmp_path):
    """A minimal persisted row (missing the result_* keys, output_path,
    demucs_skipped) must be normalized on load so the worker thread
    only ever mutates existing keys — never adds new ones — to keep
    `_save_jobs()`'s snapshot pass race-free."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    (dlc / "sloppak_converter_jobs.json").write_text(json.dumps({
        "jobs": [
            {"id": "minimal", "filename": "x.psarc", "state": "queued", "split": False},
        ]
    }))

    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    client2 = TestClient(app2)
    with client2:
        r = client2.get("/api/plugins/sloppak_converter/jobs")
    jobs = r.json()["jobs"]
    assert len(jobs) == 1
    job = jobs[0]
    for key in ("output_path", "demucs_skipped", "result_stems",
                "result_stem_count", "result_size"):
        assert key in job, f"loaded job must have {key} pre-populated"


def test_load_rejects_unsafe_filenames(plugin_routes, tmp_path):
    """A hand-edited persistence file can't sneak absolute paths, parent
    traversals, or non-.psarc filenames past the worker by going around
    the enqueue-time validation."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    (dlc / "sloppak_converter_jobs.json").write_text(json.dumps({
        "jobs": [
            {"id": "abs", "filename": "/etc/passwd", "state": "queued", "split": False},
            {"id": "trav", "filename": "../../etc/passwd", "state": "queued", "split": False},
            {"id": "trav-nested", "filename": "subdir/../../../etc/passwd",
             "state": "queued", "split": False},
            {"id": "not-psarc", "filename": "evil.exe", "state": "queued", "split": False},
            {"id": "no-ext", "filename": "evil", "state": "queued", "split": False},
            {"id": "good", "filename": "real_p.psarc", "state": "queued", "split": False},
        ]
    }))

    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    client2 = TestClient(app2)
    with client2:
        r = client2.get("/api/plugins/sloppak_converter/jobs")
    ids = sorted(j["id"] for j in r.json()["jobs"])
    assert ids == ["good"]


def test_load_default_lists_are_per_job_not_shared(plugin_routes, tmp_path):
    """Mutable defaults (result_stems) must be a fresh instance per job
    so mutating one job's list does not leak into other backfilled jobs."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    (dlc / "sloppak_converter_jobs.json").write_text(json.dumps({
        "jobs": [
            {"id": "a", "filename": "a.psarc", "state": "queued", "split": False},
            {"id": "b", "filename": "b.psarc", "state": "queued", "split": False},
        ]
    }))

    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    # Mutate one job's list directly through the live dict, then check
    # the other was unaffected.
    routes2._jobs["a"]["result_stems"].append("stem_from_a")
    assert routes2._jobs["b"]["result_stems"] == [], (
        "result_stems must be a per-job list, not a shared instance"
    )
    assert routes2._jobs["a"]["result_stems"] is not routes2._jobs["b"]["result_stems"]


def test_duplicate_setup_does_not_reload_jobs_while_worker_running(
    plugin_routes, tmp_path
):
    """If setup() is invoked again while the worker is still alive (e.g.
    a host that re-runs plugin setup on a hot-reload), the load-from-disk
    path must be skipped so it doesn't clobber the dict the running worker
    owns — clearing _jobs or demoting a running job to queued would corrupt
    in-flight state."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()

    async def _run():
        app1 = FastAPI()
        context = {"get_dlc_dir": lambda: dlc, "config_dir": dlc}
        plugin_routes._worker_task = None
        plugin_routes.setup(app1, context)
        worker_task = plugin_routes._worker_task
        assert worker_task is not None and not worker_task.done()

        # Mutate in-memory state in a way the persistence file does NOT
        # reflect (the persistence file is still empty — no enqueue ran).
        # A naive re-setup would clear this out via _load_jobs_from_disk.
        plugin_routes._jobs["in-flight"] = {
            "id": "in-flight",
            "filename": "x.psarc",
            "state": "running",
            "progress": 0.42,
        }

        app2 = FastAPI()
        plugin_routes.setup(app2, context)
        # Worker still running, dict untouched, running job still running.
        assert plugin_routes._worker_task is worker_task
        assert "in-flight" in plugin_routes._jobs
        assert plugin_routes._jobs["in-flight"]["state"] == "running"
        assert plugin_routes._jobs["in-flight"]["progress"] == 0.42

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())


def test_clear_finished_updates_persistence(plugin_routes, tmp_path):
    """After clear_finished evicts terminal jobs, the persisted file must
    reflect that — otherwise the next restart resurrects them."""
    dlc = tmp_path / "dlc"
    dlc.mkdir()
    fn = _seed_psarc(dlc, "song1_p.psarc")

    app1 = _build_app_with_dlc(plugin_routes, dlc)
    client1 = TestClient(app1)
    with client1:
        client1.post("/api/plugins/sloppak_converter/enqueue",
                     json={"filename": fn, "split": False})
        # Mark it done directly so clear_finished evicts it.
        job_id = next(iter(plugin_routes._jobs))
        plugin_routes._jobs[job_id]["state"] = "done"
        plugin_routes._save_jobs()
        client1.post("/api/plugins/sloppak_converter/clear_finished")

    routes2 = _reload_routes_module()
    app2 = _build_app_with_dlc(routes2, dlc)
    client2 = TestClient(app2)
    with client2:
        r = client2.get("/api/plugins/sloppak_converter/jobs")
    assert r.json()["jobs"] == []
