"""Profile Import plugin — imports Rocksmith 2014 player stats from encrypted profile files."""

import asyncio
import json
import sqlite3
import struct
import threading
import zlib
from pathlib import Path

from Crypto.Cipher import AES
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

# EVAS profile decryption key (well-known in the Rocksmith community)
PROFILE_KEY = bytes([
    0x72, 0x8B, 0x36, 0x9E, 0x24, 0xED, 0x01, 0x34,
    0x76, 0x85, 0x11, 0x02, 0x18, 0x12, 0xAF, 0xC0,
    0xA3, 0xC2, 0x5D, 0x02, 0x06, 0x5F, 0x16, 0x6B,
    0x4B, 0xCC, 0x58, 0xCD, 0x26, 0x44, 0xF2, 0x9E,
])

_db_path = None
_conn = None
_lock = threading.Lock()
_meta_db = None
_get_dlc_dir = None
_config_dir = None


def _get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_db_path, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS songkey_map (
                persistent_id TEXT PRIMARY KEY,
                song_key TEXT NOT NULL,
                filename TEXT NOT NULL,
                arrangement TEXT NOT NULL
            )
        """)
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_skm_songkey ON songkey_map(song_key)")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_skm_filename ON songkey_map(filename)")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imported_at TEXT DEFAULT (datetime('now')),
                profile_id TEXT,
                songs_matched INTEGER DEFAULT 0,
                favorites_imported INTEGER DEFAULT 0,
                play_counts_imported INTEGER DEFAULT 0
            )
        """)
        _conn.commit()
    return _conn


def decrypt_profile(data: bytes) -> tuple[dict, dict]:
    """Decrypt an EVAS profile file and return (header_info, profile_json).

    The file format:
      - 4 bytes: "EVAS" magic
      - 4 bytes: version (uint32 LE)
      - 8 bytes: profile ID (uint64 LE)
      - 4 bytes: uncompressed length (uint32 LE)
      - remainder: AES-256-ECB encrypted, zlib-compressed JSON
    """
    if len(data) < 20:
        raise ValueError("File too small to be a profile")
    if data[:4] != b"EVAS":
        raise ValueError("Not an EVAS profile file (bad magic)")

    version = struct.unpack("<I", data[4:8])[0]
    profile_id = struct.unpack("<Q", data[8:16])[0]
    uncompressed_len = struct.unpack("<I", data[16:20])[0]
    encrypted = data[20:]

    # AES-256-ECB, no padding
    aes = AES.new(PROFILE_KEY, AES.MODE_ECB)
    decrypted = aes.decrypt(encrypted)

    # zlib decompress
    json_bytes = zlib.decompress(decrypted)
    if json_bytes.endswith(b"\x00"):
        json_bytes = json_bytes[:-1]

    profile = json.loads(json_bytes)
    header = {
        "version": version,
        "profile_id": str(profile_id),
        "uncompressed_length": uncompressed_len,
    }
    return header, profile


def _extract_profile_summary(profile: dict) -> dict:
    """Extract a summary of importable data from a decrypted profile."""
    stats_songs = profile.get("Stats", {}).get("Songs", {})
    played_songs = {k: v for k, v in stats_songs.items() if v.get("PlayedCount", 0) > 0}
    mastered_songs = {k: v for k, v in stats_songs.items() if v.get("MasteryPeak", 0) >= 1.0}

    favorites_list = profile.get("FavoritesListRoot", {}).get("FavoritesList", [])
    song_lists = profile.get("SongListsRoot", {}).get("SongLists", [])

    songs_sa = profile.get("SongsSA", {})
    sa_played = {k: v for k, v in songs_sa.items() if v.get("PlayCount", 0) > 0}

    total_play_count = sum(v.get("PlayedCount", 0) for v in played_songs.values())
    total_sessions = int(profile.get("Stats", {}).get("SessionCnt", 0))
    total_session_time = profile.get("Stats", {}).get("SessionTime", 0)

    return {
        "total_arrangements_tracked": len(stats_songs),
        "arrangements_played": len(played_songs),
        "arrangements_mastered": len(mastered_songs),
        "total_play_count": int(total_play_count),
        "favorites_count": len(favorites_list),
        "song_lists_count": len(song_lists),
        "score_attack_played": len(sa_played),
        "total_sessions": total_sessions,
        "total_session_time": total_session_time,
    }


def setup(app: FastAPI, context: dict):
    global _db_path, _meta_db, _get_dlc_dir, _config_dir
    _config_dir = context["config_dir"]
    _db_path = str(_config_dir / "profileimport.db")
    _meta_db = context["meta_db"]
    _get_dlc_dir = context["get_dlc_dir"]

    @app.post("/api/plugins/profileimport/upload")
    async def upload_profile(request: Request):
        """Upload and decrypt a Rocksmith profile file. Returns a preview summary.

        Accepts raw binary body (the profile file bytes) with the filename
        in the X-Filename header.
        """
        data = await request.body()
        filename = request.headers.get("x-filename", "profile")
        try:
            header, profile = decrypt_profile(data)
        except Exception as e:
            return {"error": str(e)}

        summary = _extract_profile_summary(profile)
        summary["header"] = header
        summary["filename"] = filename

        # Stash the decrypted profile in memory for the import step.
        # Use the profile_id as key.
        pid = header["profile_id"]
        _stashed_profiles[pid] = profile

        return summary

    @app.get("/api/plugins/profileimport/mapping-status")
    def mapping_status():
        """Check the SongKey mapping cache status."""
        conn = _get_conn()
        count = conn.execute("SELECT COUNT(*) FROM songkey_map").fetchone()[0]
        return {"cached_mappings": count}

    @app.websocket("/ws/plugins/profileimport/build-mapping")
    async def build_mapping_ws(ws: WebSocket):
        """Build the PersistentID/SongKey → filename mapping by scanning PSARCs.
        Sends progress updates via WebSocket."""
        await ws.accept()
        try:
            await _build_mapping(ws)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await ws.send_json({"error": str(e)})
            except:
                pass

    @app.websocket("/ws/plugins/profileimport/import")
    async def import_profile_ws(ws: WebSocket):
        """Import profile stats into Slopsmith. Sends progress via WebSocket."""
        await ws.accept()
        try:
            msg = await ws.receive_json()
            profile_id = msg.get("profile_id")
            import_favorites = msg.get("import_favorites", True)
            import_play_counts = msg.get("import_play_counts", True)
            import_scores = msg.get("import_scores", True)

            profile = _stashed_profiles.get(profile_id)
            if not profile:
                await ws.send_json({"error": "Profile not found. Please re-upload."})
                return

            await _do_import(ws, profile, profile_id,
                             import_favorites, import_play_counts, import_scores)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await ws.send_json({"error": str(e)})
            except:
                pass

    @app.get("/api/plugins/profileimport/history")
    def import_history():
        """Return past import records."""
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id, imported_at, profile_id, songs_matched, favorites_imported, play_counts_imported "
            "FROM import_history ORDER BY imported_at DESC LIMIT 20"
        ).fetchall()
        return [
            {"id": r[0], "imported_at": r[1], "profile_id": r[2],
             "songs_matched": r[3], "favorites_imported": r[4],
             "play_counts_imported": r[5]}
            for r in rows
        ]

    @app.get("/api/plugins/profileimport/play-stats")
    def play_stats_summary():
        """Return aggregated play stats for the library view."""
        conn = _get_conn()
        rows = conn.execute(
            "SELECT filename, song_key, arrangement, play_count, mastery_peak, accuracy, date_last_played "
            "FROM play_stats WHERE filename IS NOT NULL "
            "ORDER BY play_count DESC LIMIT 100"
        ).fetchall()
        return [
            {"filename": r[0], "song_key": r[1], "arrangement": r[2],
             "play_count": r[3], "mastery_peak": r[4], "accuracy": r[5],
             "date_last_played": r[6]}
            for r in rows
        ]


# In-memory store for decrypted profiles between upload and import
_stashed_profiles: dict[str, dict] = {}


async def _build_mapping(ws: WebSocket):
    """Scan all PSARCs to build PersistentID/SongKey → filename mapping."""
    from psarc import read_psarc_entries

    dlc_dir = _get_dlc_dir()
    if not dlc_dir or not Path(dlc_dir).is_dir():
        await ws.send_json({"error": "DLC directory not configured"})
        return

    psarcs = sorted(Path(dlc_dir).glob("*.psarc"))
    total = len(psarcs)
    if total == 0:
        await ws.send_json({"error": "No PSARC files found in DLC directory"})
        return

    await ws.send_json({"stage": "scanning", "total": total, "progress": 0})

    conn = _get_conn()
    batch = []
    errors = 0

    for i, psarc_path in enumerate(psarcs):
        filename = psarc_path.name
        try:
            entries = read_psarc_entries(str(psarc_path), ["*.json"])
            for entry_name, entry_data in entries.items():
                try:
                    manifest = json.loads(entry_data)
                    for eid, edata in manifest.get("Entries", {}).items():
                        attrs = edata.get("Attributes", {})
                        pid = attrs.get("PersistentID", "")
                        song_key = attrs.get("SongKey", "")
                        arrangement = attrs.get("ArrangementName", "")
                        if pid and song_key and arrangement != "Vocals":
                            batch.append((pid, song_key, filename, arrangement))
                except (json.JSONDecodeError, AttributeError):
                    pass
        except Exception:
            errors += 1

        if (i + 1) % 100 == 0 or i == total - 1:
            if batch:
                with _lock:
                    conn.executemany(
                        "INSERT OR REPLACE INTO songkey_map (persistent_id, song_key, filename, arrangement) "
                        "VALUES (?, ?, ?, ?)",
                        batch,
                    )
                    conn.commit()
                batch = []

            await ws.send_json({
                "stage": "scanning",
                "total": total,
                "progress": i + 1,
                "errors": errors,
            })
            await asyncio.sleep(0)  # yield to event loop

    # Flush remaining
    if batch:
        with _lock:
            conn.executemany(
                "INSERT OR REPLACE INTO songkey_map (persistent_id, song_key, filename, arrangement) "
                "VALUES (?, ?, ?, ?)",
                batch,
            )
            conn.commit()

    final_count = conn.execute("SELECT COUNT(*) FROM songkey_map").fetchone()[0]
    await ws.send_json({
        "stage": "done",
        "total": total,
        "progress": total,
        "mappings": final_count,
        "errors": errors,
    })


async def _do_import(ws: WebSocket, profile: dict, profile_id: str,
                     import_favorites: bool, import_play_counts: bool,
                     import_scores: bool):
    """Run the actual import: favorites, play counts, and scores."""
    conn = _get_conn()

    # Check that we have a mapping
    map_count = conn.execute("SELECT COUNT(*) FROM songkey_map").fetchone()[0]
    if map_count == 0:
        await ws.send_json({"error": "SongKey mapping not built yet. Build the mapping first."})
        return

    stats = {"favorites_imported": 0, "play_counts_imported": 0, "songs_matched": 0}

    # ── Import Favorites ─────────────────────────────────────────────────
    if import_favorites:
        await ws.send_json({"stage": "favorites", "message": "Importing favorites..."})
        favorites_list = profile.get("FavoritesListRoot", {}).get("FavoritesList", [])
        existing_favs = _meta_db.favorite_set()
        imported = 0

        for song_key in favorites_list:
            # Look up filename by SongKey
            row = conn.execute(
                "SELECT DISTINCT filename FROM songkey_map WHERE song_key = ? LIMIT 1",
                (song_key,),
            ).fetchone()
            if row:
                filename = row[0]
                if filename not in existing_favs:
                    _meta_db.toggle_favorite(filename)
                    imported += 1

        stats["favorites_imported"] = imported
        await ws.send_json({
            "stage": "favorites",
            "message": f"Imported {imported} favorites (of {len(favorites_list)} in profile)",
            "done": True,
        })

    # ── Import Play Counts & Mastery ─────────────────────────────────────
    if import_play_counts:
        await ws.send_json({"stage": "playcounts", "message": "Importing play stats..."})
        stats_songs = profile.get("Stats", {}).get("Songs", {})
        played = {k: v for k, v in stats_songs.items() if v.get("PlayedCount", 0) > 0}

        # Create play_stats table in our plugin DB
        with _lock:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS play_stats (
                    persistent_id TEXT NOT NULL,
                    filename TEXT,
                    song_key TEXT,
                    arrangement TEXT,
                    play_count INTEGER DEFAULT 0,
                    mastery_peak REAL DEFAULT 0,
                    accuracy REAL DEFAULT 0,
                    date_last_played TEXT,
                    streak INTEGER DEFAULT 0,
                    PRIMARY KEY (persistent_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ps_filename ON play_stats(filename)")
            conn.commit()

        # Connect to practice journal DB to write synthetic sessions
        pj_path = str(_config_dir / "practice_journal.db")
        pj_conn = sqlite3.connect(pj_path, check_same_thread=False)
        pj_conn.execute("PRAGMA journal_mode=WAL")
        pj_conn.execute("""
            CREATE TABLE IF NOT EXISTS practice_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                title TEXT,
                artist TEXT,
                started_at TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0,
                avg_speed REAL NOT NULL DEFAULT 1.0,
                loops_used TEXT DEFAULT '[]',
                arrangement TEXT
            )
        """)
        pj_conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_filename ON practice_sessions(filename)")
        pj_conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_started ON practice_sessions(started_at)")
        pj_conn.commit()

        total = len(played)
        matched = 0
        batch = []
        pj_batch = []

        for i, (pid, song_data) in enumerate(played.items()):
            # Look up mapping
            row = conn.execute(
                "SELECT filename, song_key, arrangement FROM songkey_map WHERE persistent_id = ?",
                (pid,),
            ).fetchone()
            filename = row[0] if row else None
            song_key = row[1] if row else None
            arrangement = row[2] if row else None
            if row:
                matched += 1

            play_count = int(song_data.get("PlayedCount", 0))
            mastery = song_data.get("MasteryPeak", 0)
            accuracy = song_data.get("AccuracyGlobal", 0)
            date_las = song_data.get("DateLAS", "")

            batch.append((
                pid, filename, song_key, arrangement, play_count,
                mastery, accuracy, date_las, int(song_data.get("Streak", 0)),
            ))

            # Create a synthetic practice session for matched songs
            if filename and date_las:
                # Look up title/artist from the metadata DB
                meta_row = _meta_db.conn.execute(
                    "SELECT title, artist, duration FROM songs WHERE filename = ?",
                    (filename,),
                ).fetchone()
                title = meta_row[0] if meta_row else ""
                artist = meta_row[1] if meta_row else ""
                song_duration = meta_row[2] if meta_row else 300

                # Estimate total play time: play_count * song_duration
                # Cap at song_duration per session to keep it realistic
                total_duration = play_count * min(song_duration, 600)

                pj_batch.append((
                    filename, title, artist, date_las,
                    total_duration, 1.0, "[]", arrangement or "",
                ))

            if len(batch) >= 500:
                with _lock:
                    conn.executemany(
                        "INSERT OR REPLACE INTO play_stats "
                        "(persistent_id, filename, song_key, arrangement, play_count, "
                        "mastery_peak, accuracy, date_last_played, streak) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
                    conn.commit()
                if pj_batch:
                    pj_conn.executemany(
                        "INSERT INTO practice_sessions "
                        "(filename, title, artist, started_at, duration_seconds, avg_speed, loops_used, arrangement) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        pj_batch,
                    )
                    pj_conn.commit()
                batch = []
                pj_batch = []
                await ws.send_json({
                    "stage": "playcounts",
                    "total": total,
                    "progress": i + 1,
                    "matched": matched,
                })
                await asyncio.sleep(0)

        # Flush remaining
        if batch:
            with _lock:
                conn.executemany(
                    "INSERT OR REPLACE INTO play_stats "
                    "(persistent_id, filename, song_key, arrangement, play_count, "
                    "mastery_peak, accuracy, date_last_played, streak) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                conn.commit()
        if pj_batch:
            pj_conn.executemany(
                "INSERT INTO practice_sessions "
                "(filename, title, artist, started_at, duration_seconds, avg_speed, loops_used, arrangement) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                pj_batch,
            )
            pj_conn.commit()

        pj_conn.close()

        stats["play_counts_imported"] = total
        stats["songs_matched"] = matched
        await ws.send_json({
            "stage": "playcounts",
            "message": f"Imported {total} play records ({matched} matched to library, fed to practice journal)",
            "done": True,
        })

    # ── Import Score Attack ──────────────────────────────────────────────
    if import_scores:
        await ws.send_json({"stage": "scores", "message": "Importing Score Attack data..."})
        songs_sa = profile.get("SongsSA", {})
        sa_played = {k: v for k, v in songs_sa.items() if v.get("PlayCount", 0) > 0}

        with _lock:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS score_attack (
                    persistent_id TEXT NOT NULL,
                    filename TEXT,
                    song_key TEXT,
                    arrangement TEXT,
                    play_count INTEGER DEFAULT 0,
                    high_score_easy INTEGER DEFAULT 0,
                    high_score_medium INTEGER DEFAULT 0,
                    high_score_hard INTEGER DEFAULT 0,
                    high_score_master INTEGER DEFAULT 0,
                    badge_easy INTEGER DEFAULT 0,
                    badge_medium INTEGER DEFAULT 0,
                    badge_hard INTEGER DEFAULT 0,
                    badge_master INTEGER DEFAULT 0,
                    PRIMARY KEY (persistent_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sa_filename ON score_attack(filename)")
            conn.commit()

        batch = []
        sa_matched = 0
        for pid, sa_data in sa_played.items():
            row = conn.execute(
                "SELECT filename, song_key, arrangement FROM songkey_map WHERE persistent_id = ?",
                (pid,),
            ).fetchone()
            if row:
                sa_matched += 1
            scores = sa_data.get("HighScores", {})
            badges = sa_data.get("Badges", {})
            batch.append((
                pid,
                row[0] if row else None,
                row[1] if row else None,
                row[2] if row else None,
                int(sa_data.get("PlayCount", 0)),
                int(scores.get("Easy", 0)),
                int(scores.get("Medium", 0)),
                int(scores.get("Hard", 0)),
                int(scores.get("Master", 0)),
                int(badges.get("Easy", 0)),
                int(badges.get("Medium", 0)),
                int(badges.get("Hard", 0)),
                int(badges.get("Master", 0)),
            ))

        if batch:
            with _lock:
                conn.executemany(
                    "INSERT OR REPLACE INTO score_attack "
                    "(persistent_id, filename, song_key, arrangement, play_count, "
                    "high_score_easy, high_score_medium, high_score_hard, high_score_master, "
                    "badge_easy, badge_medium, badge_hard, badge_master) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                conn.commit()

        await ws.send_json({
            "stage": "scores",
            "message": f"Imported {len(sa_played)} Score Attack records ({sa_matched} matched)",
            "done": True,
        })

    # ── Record import history ────────────────────────────────────────────
    with _lock:
        conn.execute(
            "INSERT INTO import_history (profile_id, songs_matched, favorites_imported, play_counts_imported) "
            "VALUES (?, ?, ?, ?)",
            (profile_id, stats["songs_matched"], stats["favorites_imported"],
             stats["play_counts_imported"]),
        )
        conn.commit()

    # Clean up stashed profile
    _stashed_profiles.pop(profile_id, None)

    await ws.send_json({
        "stage": "complete",
        "stats": stats,
    })
