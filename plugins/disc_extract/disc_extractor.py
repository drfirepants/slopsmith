#!/usr/bin/env python3
"""Extract Rocksmith 2014 base game songs from songs.psarc into individual CDLC PSARCs.

Splits the ~56 on-disc songs bundled in songs.psarc into standalone per-song
PSARCs that Slopsmith can index and play individually.

Usage:
    python disc_extractor.py [--output DIR] [--songs KEY,KEY,...]
"""

import argparse
import fnmatch
import json
import logging
import re
import struct
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from psarc import _parse_toc, _extract_entry
from patcher import pack_psarc

log = logging.getLogger("slopsmith.plugin.discextract")

RS_DIR = Path.home() / ".local/share/Steam/steamapps/common/Rocksmith2014"
DLC_DIR = RS_DIR / "dlc"
SONGS_PSARC = RS_DIR / "songs.psarc"

APPID = "221680"
MANIFEST_DIR = "songs"


class PsarcReader:
    """Lazy PSARC reader - parses TOC once, extracts entries on demand."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.f = open(filepath, "rb")
        self.entries, self.filenames, self.block_sizes, self.block_size = _parse_toc(
            self.f
        )
        self.name_map = {}
        for i, name in enumerate(self.filenames):
            name = name.strip()
            if name:
                self.name_map[name] = i

    def get(self, name):
        if name not in self.name_map:
            return None
        idx = self.name_map[name]
        entry = self.entries[idx + 1]
        return _extract_entry(self.f, entry, self.block_sizes, self.block_size)

    def get_matching(self, patterns):
        result = {}
        for name in self.name_map:
            if any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns):
                data = self.get(name)
                if data is not None:
                    result[name] = data
        return result

    def list_files(self):
        return list(self.name_map.keys())

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def parse_bnk_wem_id(bnk_data):
    """Parse a Wwise BNK file and return the DIDX media ID."""
    offset = 0
    while offset + 8 <= len(bnk_data):
        chunk_id = bnk_data[offset : offset + 4]
        chunk_size = struct.unpack("<I", bnk_data[offset + 4 : offset + 8])[0]
        if chunk_id == b"DIDX" and chunk_size >= 12:
            media_id = struct.unpack("<I", bnk_data[offset + 8 : offset + 12])[0]
            return media_id
        offset += 8 + chunk_size
    return None


def sanitize_filename(name):
    """Make a string safe for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def get_song_info(manifest_data):
    """Extract artist name, song name, and song key from a manifest JSON."""
    m = json.loads(manifest_data)
    attrs = list(m["Entries"].values())[0]["Attributes"]
    return {
        "artist": attrs.get("ArtistName", "Unknown"),
        "title": attrs.get("SongName", "Unknown"),
        "song_key": attrs.get("SongKey", ""),
        "year": attrs.get("SongYear", 0),
    }


def build_hsan(manifest_entries, hsan_entries, song_key_lower):
    """Build a per-song HSAN from the shared HSAN, filtered to this song's arrangements."""
    filtered = {}
    for pid, entry in hsan_entries.items():
        attrs = entry.get("Attributes", entry)
        manifest_urn = attrs.get("ManifestUrn", "")
        urn_name = manifest_urn.rsplit(":", 1)[-1] if ":" in manifest_urn else ""
        if urn_name.startswith(song_key_lower + "_") or urn_name == song_key_lower:
            filtered[pid] = entry
    return json.dumps({"Entries": filtered}, indent=2)


def build_aggregate_graph(song_key_lower, manifest_names, sng_names, dds_names,
                          has_showlights, xblock_name):
    """Generate the aggregate graph (.nt) for a standalone CDLC PSARC."""
    lines = []
    dlc_key = f"songs_dlc_{song_key_lower}"

    def entry(tags, canonical, name, relpath, llid=None, logpath=None):
        u = f"urn:uuid:{uuid.uuid4()}"
        for tag in tags:
            lines.append(f'<{u}> <http://emergent.net/aweb/1.0/tag> "{tag}".')
        lines.append(f'<{u}> <http://emergent.net/aweb/1.0/canonical> "{canonical}".')
        lines.append(f'<{u}> <http://emergent.net/aweb/1.0/name> "{name}".')
        lines.append(f'<{u}> <http://emergent.net/aweb/1.0/relpath> "{relpath}".')
        if llid:
            lines.append(f'<{u}> <http://emergent.net/aweb/1.0/llid> "{llid}".')
        if logpath:
            lines.append(f'<{u}> <http://emergent.net/aweb/1.0/logpath> "{logpath}".')

    # JSON manifests
    for mname in manifest_names:
        entry(
            ["database", "json-db"],
            f"/manifests/{dlc_key}",
            mname,
            f"/manifests/{dlc_key}/{mname}.json",
        )

    # HSAN
    entry(
        ["database", "hsan-db"],
        f"/manifests/{dlc_key}",
        dlc_key,
        f"/manifests/{dlc_key}/{dlc_key}.hsan",
    )

    # Showlights
    if has_showlights:
        llid = f"{uuid.uuid4().hex[:8]}-0000-0000-0000-000000000000"
        entry(
            ["application", "xml"],
            "/songs/arr",
            f"{song_key_lower}_showlights",
            f"/songs/arr/{song_key_lower}_showlights.xml",
            llid,
            f"/songs/arr/{song_key_lower}_showlights.xml",
        )

    # SNG files
    for sname in sng_names:
        llid = f"{uuid.uuid4().hex[:8]}-0000-0000-0000-000000000000"
        entry(
            ["application", "musicgame-song"],
            "/songs/bin/generic",
            sname,
            f"/songs/bin/generic/{sname}.sng",
            llid,
            f"/songs/bin/generic/{sname}.sng",
        )

    # Album art
    for dname in dds_names:
        llid = f"{uuid.uuid4().hex[:8]}-0000-0000-0000-000000000000"
        entry(
            ["dds", "image"],
            "/gfxassets/album_art",
            dname,
            f"/gfxassets/album_art/{dname}.dds",
            llid,
            f"/gfxassets/album_art/{dname}.dds",
        )

    # Song BNK
    llid = f"{uuid.uuid4().hex[:8]}-0000-0000-0000-000000000000"
    entry(
        ["audio", "wwise-sound-bank", "dx9"],
        "/audio/windows",
        f"song_{song_key_lower}",
        f"/audio/windows/song_{song_key_lower}.bnk",
        llid,
        f"/audio/song_{song_key_lower}.bnk",
    )

    # Preview BNK
    llid = f"{uuid.uuid4().hex[:8]}-0000-0000-0000-000000000000"
    entry(
        ["audio", "wwise-sound-bank", "dx9"],
        "/audio/windows",
        f"song_{song_key_lower}_preview",
        f"/audio/windows/song_{song_key_lower}_preview.bnk",
        llid,
        f"/audio/song_{song_key_lower}_preview.bnk",
    )

    # Xblock
    entry(
        ["emergent-world", "x-world"],
        "/gamexblocks/nsongs",
        song_key_lower,
        f"/gamexblocks/nsongs/{xblock_name}",
    )

    return "\n".join(lines) + "\n"


def update_xblock(xblock_data, old_hsan_name, new_hsan_name):
    """Update the HSAN URN reference in an xblock."""
    text = xblock_data.decode("utf-8")
    text = text.replace(
        f"urn:database:hsan-db:{old_hsan_name}",
        f"urn:database:hsan-db:{new_hsan_name}",
    )
    return text.encode("utf-8")


def process_songs(reader, output_dir, filter_keys=None):
    """Process songs.psarc and extract each song into a standalone CDLC PSARC."""
    # Get song list from xblocks
    xblock_files = {
        name: name.rsplit("/", 1)[-1]
        for name in reader.list_files()
        if name.startswith("gamexblocks/nsongs/") and name.endswith(".xblock")
    }

    song_keys = []
    for path, fname in sorted(xblock_files.items()):
        key = fname.replace(".xblock", "")
        song_keys.append((key, path, fname))

    if filter_keys:
        filter_set = {k.lower() for k in filter_keys}
        song_keys = [(k, p, f) for k, p, f in song_keys if k in filter_set]

    log.info("Found %d songs", len(song_keys))

    # Load shared resources
    flat_root = reader.get("flatmodels/rs/rsenumerable_root.flat")
    flat_song = reader.get("flatmodels/rs/rsenumerable_song.flat")

    # Load the shared HSAN
    hsan_path = f"manifests/{MANIFEST_DIR}/{MANIFEST_DIR}.hsan"
    hsan_raw = reader.get(hsan_path)
    hsan_data = json.loads(hsan_raw) if hsan_raw else {"Entries": {}}
    hsan_entries = hsan_data.get("Entries", {})

    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = 0

    for i, (key, xblock_path, xblock_fname) in enumerate(song_keys):
        # Gather files for this song
        manifests = reader.get_matching([f"manifests/{MANIFEST_DIR}/{key}_*.json"])
        sngs = reader.get_matching([f"songs/bin/generic/{key}_*.sng"])
        album_art = reader.get_matching([f"gfxassets/album_art/album_{key}_*.dds"])
        showlights_path = f"songs/arr/{key}_showlights.xml"
        showlights = reader.get(showlights_path)
        xblock_data = reader.get(xblock_path)

        if not manifests:
            log.warning("[%d/%d] %s: no manifests found, skipping", i + 1, len(song_keys), key)
            continue

        # Get song info from first non-vocals manifest
        info = None
        for mpath, mdata in sorted(manifests.items()):
            if "_vocals" not in mpath:
                info = get_song_info(mdata)
                break
        if not info:
            info = get_song_info(list(manifests.values())[0])

        artist = sanitize_filename(info["artist"])
        title = sanitize_filename(info["title"])
        out_name = f"{title} - {artist}_p.psarc"

        # Skip if already extracted
        if (output_dir / out_name).exists():
            extracted += 1
            log.info("[%d/%d] %s - %s (already exists)", i + 1, len(song_keys), info["artist"], info["title"])
            continue

        # Get audio (self-contained in songs.psarc)
        song_bnk_name = f"audio/windows/song_{key}.bnk"
        preview_bnk_name = f"audio/windows/song_{key}_preview.bnk"
        song_bnk = reader.get(song_bnk_name)
        preview_bnk = reader.get(preview_bnk_name)

        if not song_bnk:
            log.warning("[%d/%d] %s: no song BNK found, skipping", i + 1, len(song_keys), key)
            continue

        # Parse BNK to find WEM IDs
        song_wem_id = parse_bnk_wem_id(song_bnk)
        preview_wem_id = parse_bnk_wem_id(preview_bnk) if preview_bnk else None

        # Get WEM files
        wem_files = {}
        if song_wem_id:
            wem_name = f"audio/windows/{song_wem_id}.wem"
            wem_data = reader.get(wem_name)
            if wem_data:
                wem_files[wem_name] = wem_data

        if preview_wem_id and preview_wem_id != song_wem_id:
            wem_name = f"audio/windows/{preview_wem_id}.wem"
            wem_data = reader.get(wem_name)
            if wem_data:
                wem_files[wem_name] = wem_data

        if not wem_files:
            log.warning("[%d/%d] %s: no WEM audio found, skipping", i + 1, len(song_keys), key)
            continue

        # Build the standalone PSARC structure in a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            dlc_key = f"songs_dlc_{key}"

            # appid
            (tmpdir / "appid.appid").write_text(APPID)

            # Audio files
            audio_dir = tmpdir / "audio" / "windows"
            audio_dir.mkdir(parents=True)
            (audio_dir / f"song_{key}.bnk").write_bytes(song_bnk)
            if preview_bnk:
                (audio_dir / f"song_{key}_preview.bnk").write_bytes(preview_bnk)
            for wem_path, wem_data in wem_files.items():
                wem_fname = wem_path.rsplit("/", 1)[-1]
                (audio_dir / wem_fname).write_bytes(wem_data)

            # Flat models
            flat_dir = tmpdir / "flatmodels" / "rs"
            flat_dir.mkdir(parents=True)
            if flat_root:
                (flat_dir / "rsenumerable_root.flat").write_bytes(flat_root)
            if flat_song:
                (flat_dir / "rsenumerable_song.flat").write_bytes(flat_song)

            # Xblock (update HSAN URN from shared to per-song)
            xblock_dir = tmpdir / "gamexblocks" / "nsongs"
            xblock_dir.mkdir(parents=True)
            updated_xblock = update_xblock(xblock_data, MANIFEST_DIR, dlc_key)
            (xblock_dir / xblock_fname).write_bytes(updated_xblock)

            # Album art
            art_dir = tmpdir / "gfxassets" / "album_art"
            art_dir.mkdir(parents=True)
            for art_path, art_data in album_art.items():
                art_fname = art_path.rsplit("/", 1)[-1]
                (art_dir / art_fname).write_bytes(art_data)

            # Manifests (relocated to per-song directory)
            manifest_out_dir = tmpdir / "manifests" / dlc_key
            manifest_out_dir.mkdir(parents=True)

            manifest_names = []
            for mpath, mdata in manifests.items():
                mfname = mpath.rsplit("/", 1)[-1]
                mname = mfname.replace(".json", "")
                manifest_names.append(mname)
                (manifest_out_dir / mfname).write_bytes(mdata)

            # Per-song HSAN
            hsan_content = build_hsan(manifests, hsan_entries, key)
            (manifest_out_dir / f"{dlc_key}.hsan").write_text(hsan_content)

            # Showlights
            arr_dir = tmpdir / "songs" / "arr"
            arr_dir.mkdir(parents=True)
            if showlights:
                (arr_dir / f"{key}_showlights.xml").write_bytes(showlights)

            # SNG files
            sng_dir = tmpdir / "songs" / "bin" / "generic"
            sng_dir.mkdir(parents=True)
            sng_names = []
            for sng_path, sng_data in sngs.items():
                sng_fname = sng_path.rsplit("/", 1)[-1]
                sng_name = sng_fname.replace(".sng", "")
                sng_names.append(sng_name)
                (sng_dir / sng_fname).write_bytes(sng_data)

            # DDS names for aggregate graph
            dds_names = []
            for art_path in album_art:
                dds_fname = art_path.rsplit("/", 1)[-1].replace(".dds", "")
                dds_names.append(dds_fname)

            # Aggregate graph
            ag = build_aggregate_graph(
                key, manifest_names, sng_names, dds_names,
                showlights is not None, xblock_fname,
            )
            (tmpdir / f"{key}_aggregategraph.nt").write_text(ag)

            # Pack PSARC
            out_path = output_dir / out_name
            pack_psarc(tmpdir, out_path)
            extracted += 1

            arrangements = len(sngs)
            log.info(
                "[%d/%d] %s - %s (%d arr) -> %s",
                i + 1, len(song_keys), info["artist"], info["title"], arrangements, out_name,
            )

    reader.close()
    return extracted


def main():
    parser = argparse.ArgumentParser(
        description="Extract Rocksmith 2014 base game songs into individual CDLC PSARCs"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=DLC_DIR,
        help="Output directory (default: dlc/)",
    )
    parser.add_argument(
        "--songs",
        help="Comma-separated list of song keys to extract (e.g. bloodandthunder,goingdowntheroad)",
    )
    args = parser.parse_args()

    filter_keys = None
    if args.songs:
        filter_keys = [k.strip().lower() for k in args.songs.split(",")]

    if not SONGS_PSARC.exists():
        log.error("songs.psarc not found at %s", SONGS_PSARC)
        sys.exit(1)

    log.info("Opening %s...", SONGS_PSARC.name)
    reader = PsarcReader(SONGS_PSARC)

    log.info("Extracting base game songs from songs.psarc")
    count = process_songs(reader, args.output, filter_keys)
    log.info("Done! %d songs extracted to %s", count, args.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    main()
