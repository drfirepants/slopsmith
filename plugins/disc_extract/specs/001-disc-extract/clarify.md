# Clarifications — Base Game Song Extractor

## Q1: What happens to the WebSocket stream if the user closes the tab mid-extraction?
**A**: `[OPEN]` — `routes.py` would need inspection at the `WebSocketDisconnect` handler. Best behaviour: server keeps writing PSARCs, client reconnect sees updated `extracted_count` on next status load. The README implies "Skips already-extracted songs" is the recovery path.

## Q2: Are JVocals / Bonus arrangements ever surfaced?
**A**: No. `routes.py` filters out `Vocals`, `ShowLights`, `JVocals` from the listing. Bonus arrangements are kept since they're still playable.

## Q3: How is the Rocksmith install located on Windows / macOS hosts?
**A**: `disc_extractor.py`+`routes.py` use `_find_rs_dir`: Docker mount `/rocksmith` first, then `dlc_dir.parent` if its name is `Rocksmith2014`, then a small list of common Steam paths (Linux home, Windows Program Files). Native (non-Docker) Linux/Steam installs work; native Windows works if Steam is in a default location.

## Q4: What's the file name format for extracted PSARCs?
**A**: `{Title} - {Artist}_p.psarc` (per README and `screen.js`). The `_p.psarc` suffix is the Rocksmith PC platform suffix.

## Q5: Are extracted PSARCs DD-enabled?
**A**: Whatever was in the source `songs.psarc` (the extractor copies SNG / manifests verbatim). [NEEDS CLARIFICATION] — confirm by extracting a known-DD song and checking the resulting PSARC.

## Q6: Does the extractor produce `_m.psarc` (Mac) variants?
**A**: No — only `_p.psarc` (PC). The source `songs.psarc` on a Steam install is PC-platform; cross-platform repacking is out of scope.

## Q7: Is metadata cached automatically post-extraction?
**A**: Yes. Per README ("Auto-caches metadata for new extractions into Slopsmith library") and `routes.py` `setup` capturing `extract_meta` + `meta_db` from context.

## Q8: Plugin slug vs id — is there drift?
**A**: No. `plugin.json` id is `disc_extract`, README and dir name align (`disc_extract`). API routes use `disc_extract`, JS hook key is `__slopsmithDiscExtractHooksInstalled` (camelCase variant — fine, it's a private window key).
