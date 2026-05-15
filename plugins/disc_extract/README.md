# Base Game Song Extractor

Slopsmith plugin that extracts Rocksmith 2014's ~56 on-disc songs from `songs.psarc` into individual CDLC PSARCs that Slopsmith can index and play.

## Features

- Reads `songs.psarc` and lists all base game songs with arrangements
- Extracts each song into a standalone `{Title} - {Artist}_p.psarc`
- Includes all assets: SNG, manifests, album art, audio (BNK + WEM), showlights, xblock
- Builds proper aggregate graph and per-song HSAN for game compatibility
- Skips already-extracted songs
- Auto-caches metadata for new extractions into Slopsmith library
- Real-time progress via WebSocket

## Requirements

- Rocksmith 2014 installed with `songs.psarc` accessible
- Docker: Rocksmith directory mounted at `/rocksmith:ro`

## Install

```bash
cd plugins/
git clone https://github.com/byrongamatos/slopsmith-plugin-discextract.git disc_extract
```

## Docker Setup

Mount your Rocksmith 2014 directory (already done if you have the RS1 extractor):

```yaml
volumes:
  - /path/to/Rocksmith2014:/rocksmith:ro
```
