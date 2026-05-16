"""Tab Import plugin — drag and drop Guitar Pro files to create CDLC."""

import asyncio
import base64
import os
import re
import tempfile
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

_get_dlc_dir = None
_extract_meta = None
_meta_db = None


def _parse_timestamp(ts: str) -> float | None:
    """Convert 'mm:ss', 'hh:mm:ss', or plain seconds string to float seconds."""
    if not ts:
        return None
    try:
        parts = ts.strip().split(":")
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except Exception:
        return None


def _download_youtube_audio(youtube_url: str, out_dir: str, report,
                             start_time: str = "", end_time: str = "") -> str:
    """Download audio from a YouTube URL using yt-dlp. Returns path to OGG file."""
    import yt_dlp
    import subprocess

    start_sec = _parse_timestamp(start_time)
    end_sec = _parse_timestamp(end_time)

    out_path = os.path.join(out_dir, "yt_audio")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "vorbis",
            "preferredquality": "5",
        }],
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [lambda d: report(
            f"Downloading: {d.get('_percent_str', '').strip()}",
            None,
        ) if d["status"] == "downloading" else None],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    # Find the downloaded file
    ogg = out_path + ".ogg"
    if not Path(ogg).exists():
        candidates = list(Path(out_dir).glob("yt_audio.*"))
        if not candidates:
            raise RuntimeError("yt-dlp did not produce an audio file")
        ogg = str(candidates[0])

    # Trim with ffmpeg if start/end times were specified
    if start_sec is not None or end_sec is not None:
        trimmed = os.path.join(out_dir, "yt_audio_trimmed.ogg")
        cmd = ["ffmpeg", "-y", "-i", ogg]
        if start_sec is not None:
            cmd += ["-ss", str(start_sec)]
        if end_sec is not None:
            # end_sec is relative to original; adjust for start offset
            duration = end_sec - (start_sec or 0)
            cmd += ["-t", str(duration)]
        cmd += ["-c", "copy", trimmed]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and Path(trimmed).exists():
            os.replace(trimmed, ogg)
        else:
            raise RuntimeError(f"ffmpeg trim failed: {result.stderr.decode()[:200]}")

    return ogg


def setup(app, context):
    global _get_dlc_dir, _extract_meta, _meta_db
    _get_dlc_dir = context["get_dlc_dir"]
    _extract_meta = context["extract_meta"]
    _meta_db = context["meta_db"]

    @app.post("/api/plugins/tab_import/upload")
    async def upload_tab(data: dict):
        """Receive a GP file as base64, return parsed track info."""
        filename = data.get("filename", "")
        b64 = data.get("data", "")
        if not filename or not b64:
            return {"error": "No file data"}

        try:
            gp_data = base64.b64decode(b64)
        except Exception:
            return {"error": "Invalid file data"}

        ext = Path(filename).suffix.lower()
        if ext not in ('.gp3', '.gp4', '.gp5'):
            return {"error": f"Unsupported format ({ext}). Only GP3, GP4, GP5 are supported."}

        # Save to temp and parse
        tmp = Path(tempfile.mkdtemp()) / filename
        tmp.write_bytes(gp_data)

        try:
            import guitarpro
            song = guitarpro.parse(str(tmp))

            from gp2rs import auto_select_tracks
            track_indices, name_map = auto_select_tracks(str(tmp))

            tracks = []
            for i, track in enumerate(song.tracks):
                is_selected = i in track_indices
                arr_name = name_map.get(i, "")
                tracks.append({
                    "index": i,
                    "name": track.name,
                    "strings": track.strings and len(track.strings) or 0,
                    "is_guitar": is_selected,
                    "arrangement": arr_name,
                })

            return {
                "title": song.title or Path(filename).stem,
                "artist": song.artist or "Unknown",
                "album": song.album or "",
                "tracks": tracks,
                "tmp_path": str(tmp),
            }
        except Exception as e:
            return {"error": f"Failed to parse: {e}"}

    @app.websocket("/ws/plugins/tab_import/build")
    async def ws_build_tab(websocket: WebSocket, tmp_path: str, title: str = "",
                           artist: str = "", album: str = "", tracks: str = "",
                           arrangement_names: str = "", youtube_url: str = "",
                           youtube_start: str = "", youtube_end: str = ""):
        """Build CDLC from an uploaded GP file with progress."""
        await websocket.accept()

        dlc = _get_dlc_dir()
        if not dlc:
            await websocket.send_json({"error": "DLC folder not configured"})
            await websocket.close()
            return

        if not Path(tmp_path).exists():
            await websocket.send_json({"error": "File expired — please upload again"})
            await websocket.close()
            return

        # Parse track indices and user-supplied arrangement names
        try:
            track_indices = [int(x) for x in tracks.split(",") if x.strip()]
        except Exception:
            track_indices = []
        ui_names = [x.strip() for x in arrangement_names.split(",") if x.strip()]
        ui_name_map = dict(zip(track_indices, ui_names)) if ui_names else {}

        progress_queue = asyncio.Queue()

        def _do_build():
            def report(stage, pct):
                msg = {"stage": stage}
                if pct is not None:
                    msg["progress"] = pct
                progress_queue.put_nowait(msg)

            try:
                gp_path = tmp_path

                report("Parsing Guitar Pro file...", 10)
                from gp2rs import convert_file, auto_select_tracks
                from gp2midi import gp_to_audio
                from cdlc_builder import build_cdlc
                import guitarpro

                song = guitarpro.parse(gp_path)

                if not track_indices:
                    auto_indices, name_map = auto_select_tracks(gp_path)
                else:
                    auto_indices = track_indices
                    from gp2rs import is_drum_track
                    name_map = {}
                    for i in auto_indices:
                        if i in ui_name_map:
                            name_map[i] = ui_name_map[i]
                        else:
                            t = song.tracks[i]
                            tname = t.name.lower()
                            if is_drum_track(t):
                                name_map[i] = 'Drums'
                            elif 'bass' in tname:
                                name_map[i] = 'Bass'
                            elif 'rhythm' in tname:
                                name_map[i] = 'Rhythm'
                            else:
                                name_map[i] = 'Lead'

                if not auto_indices:
                    progress_queue.put_nowait({"error": "No guitar/bass tracks found"})
                    return

                arr_names = [name_map.get(i, "Lead") for i in auto_indices]
                report(f"Selected {len(auto_indices)} tracks: {', '.join(arr_names)}", 20)

                # Audio: YouTube download or MIDI fallback
                use_youtube = bool(youtube_url and youtube_url.strip())
                if use_youtube:
                    report("Downloading audio from YouTube...", 25)
                    yt_dir = tempfile.mkdtemp()
                    try:
                        audio_path = _download_youtube_audio(youtube_url.strip(), yt_dir, report,
                                                              start_time=youtube_start,
                                                              end_time=youtube_end)
                        report("YouTube audio downloaded.", 40)
                    except Exception as e:
                        progress_queue.put_nowait({"error": f"YouTube download failed: {e}"})
                        return
                else:
                    report("Generating MIDI audio...", 30)
                    midi_out = os.path.join(tempfile.mkdtemp(), "midi")
                    audio_path = gp_to_audio(gp_path, midi_out)

                report("Converting to Rocksmith XML...", 50)
                xml_dir = tempfile.mkdtemp()
                xml_files = convert_file(gp_path, xml_dir,
                                         track_indices=auto_indices,
                                         audio_offset=0.0,
                                         arrangement_names=name_map)

                t = title or song.title or Path(gp_path).stem
                a = artist or song.artist or "Unknown"
                al = album or song.album or ""
                safe_t = re.sub(r'[<>:"/\\|?*]', '_', t)
                safe_a = re.sub(r'[<>:"/\\|?*]', '_', a)
                suffix = "_p" if use_youtube else "_midi_p"
                output = str(dlc / f"{safe_t}_{safe_a}{suffix}.psarc")
                song_title = t if use_youtube else f"{t} (MIDI)"

                def on_progress(msg, pct):
                    report(msg, 60 + pct * 0.35)

                report("Compiling SNG and packing PSARC...", 60)
                build_cdlc(
                    xml_paths=xml_files,
                    arrangement_names=arr_names,
                    audio_path=audio_path,
                    title=song_title,
                    artist=a,
                    album=al,
                    output_path=output,
                    on_progress=on_progress,
                )

                # Cache metadata
                try:
                    out_path = Path(output)
                    meta = _extract_meta(out_path)
                    stat = out_path.stat()
                    _meta_db.put(out_path.name, stat.st_mtime, stat.st_size, meta)
                except Exception:
                    pass

                progress_queue.put_nowait({
                    "done": True, "progress": 100, "stage": "Complete!",
                    "filename": Path(output).name,
                    "tracks": ", ".join(arr_names),
                })

            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_queue.put_nowait({"error": str(e)})

        loop = asyncio.get_event_loop()
        build_task = loop.run_in_executor(None, _do_build)

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    await websocket.send_json(msg)
                    if msg.get("done") or msg.get("error"):
                        break
                except asyncio.TimeoutError:
                    if build_task.done():
                        break
        except WebSocketDisconnect:
            pass

        await websocket.close()
