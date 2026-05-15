# Slopsmith Plugin: RS1 Song Extractor

A plugin for [Slopsmith](https://github.com/byrongamatos/slopsmith) that extracts Rocksmith 1 compatibility songs from multi-song PSARCs into individual playable CDLCs.

## What It Does

Rocksmith 2014 ships RS1 compatibility packs as large multi-song PSARC files (143+ songs in one file). Slopsmith can't browse or play individual songs from these mega-packs. This plugin splits them into standalone per-song PSARCs that appear as individual entries in your library.

## Features

- **Auto-detection** — finds RS1 compatibility packs in your DLC folder
- **Song browser** — shows all songs inside each pack with artist, title, and arrangements
- **One-click extraction** — extract all songs from a pack or all packs at once
- **Audio matching** — pulls song audio (BNK + WEM) from songs.psarc and matches it to each song by parsing Wwise BNK media IDs
- **Proper PSARC structure** — creates standalone CDLCs with per-song HSAN, aggregate graph, updated xblock URNs, relocated manifests
- **Skip existing** — songs already extracted are skipped on re-runs
- **Library integration** — newly extracted songs are automatically scanned into the library
- **Real-time progress** — shows extraction progress per song

## Requirements

- RS1 compatibility pack(s) in your DLC folder:
  - `rs1compatibilitydlc_p.psarc` (RS1 DLC songs)
  - `rs1compatibilitydisc_p.psarc` (RS1 disc songs)
- `songs.psarc` in the Rocksmith 2014 install directory (contains audio for DLC pack songs)
- The DLC folder must be inside the Rocksmith2014 directory for audio matching to work

## Installation

```bash
cd /path/to/slopsmith/plugins
git clone https://github.com/byrongamatos/slopsmith-plugin-rs1extract.git rs1_extract
docker compose restart
```

The "RS1 Import" link will appear in the navigation bar.

## Docker Setup

The Rocksmith install directory must be accessible from Docker. If your DLC folder is mounted at `/dlc`, the parent directory should contain `songs.psarc`. Example docker-compose:

```yaml
volumes:
  - /path/to/Rocksmith2014/dlc:/dlc
```

Or mount the entire Rocksmith directory:

```yaml
volumes:
  - /path/to/Rocksmith2014:/rocksmith
environment:
  - DLC_DIR=/rocksmith/dlc
```

## License

MIT
