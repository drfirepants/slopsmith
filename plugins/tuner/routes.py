"""Tuner plugin — persist last selected tuning in config_dir."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import FastAPI, Request

DEFAULT_TUNING = "Guitar Standard"

DEFAULT_TUNINGS = {
    "Guitar": {
        "Guitar Standard": [82.41, 110.00, 146.83, 196.00, 246.94, 329.63],
        "Guitar Drop D": [73.42, 110.00, 146.83, 196.00, 246.94, 329.63],
        "Guitar Open G": [73.42, 98.00, 146.83, 196.00, 246.94, 293.66],
        "Guitar DADGAD": [73.42, 110.00, 146.83, 196.00, 220.00, 293.66],
        "Guitar Open E": [82.41, 123.47, 164.81, 207.65, 246.94, 329.63]
    },
    "Bass 4-string": {
        "Bass 4-string Standard": [41.20, 55.00, 73.42, 98.00],
        "Bass 4-string Drop D": [36.71, 55.00, 73.42, 98.00],
        "Bass 4-string D-Standard": [36.71, 48.99, 65.41, 87.31],
        "Bass 4-string Drop C": [32.70, 48.99, 65.41, 87.31],
    },
    "Bass 5-string": {
        "Bass 5-string Standard": [30.87, 41.20, 55.00, 73.42, 98.00],
        "Bass 5-string Drop D": [30.87, 36.71, 55.00, 73.42, 98.00],
        "Bass 5-string D-Standard": [27.50, 36.71, 48.99, 65.41, 87.31],
        "Bass 5-string Drop C": [27.50, 32.70, 48.99, 65.41, 87.31],
    }
}

def setup(app: FastAPI, context: dict):
    config_dir = Path(context["config_dir"])
    config_file = config_dir / "tuner.json"

    def _read() -> dict:
        defaults = {
            "lastTuning": DEFAULT_TUNING,
            "customTunings": {},
            "disabledTunings": [],
            "showFloatingButton": True
        }
        if not config_file.exists():
            return defaults
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return defaults
            
            res = {}
            res["lastTuning"] = str(data.get("lastTuning", DEFAULT_TUNING))
            res["customTunings"] = data.get("customTunings", {})
            res["disabledTunings"] = data.get("disabledTunings", [])
            res["showFloatingButton"] = bool(data.get("showFloatingButton", True))
            
            if not isinstance(res["customTunings"], dict):
                res["customTunings"] = {}
            if not isinstance(res["disabledTunings"], list):
                res["disabledTunings"] = []
                
            return res
        except Exception:
            return defaults

    def _write(data: dict) -> None:
        config_dir.mkdir(parents=True, exist_ok=True)
        # Merge with existing to be safe, or just overwrite if we have full object
        current = _read()
        # Remove defaultTunings from data before writing to file if it's there
        # as it is a computed property from the backend
        if "defaultTunings" in data:
            data = data.copy()
            del data["defaultTunings"]
        current.update(data)
        config_file.write_text(json.dumps(current, indent=2), encoding="utf-8")

    @app.get("/api/plugins/tuner/config")
    def get_config():
        config = _read()
        config["defaultTunings"] = DEFAULT_TUNINGS
        return config

    @app.post("/api/plugins/tuner/config")
    async def set_config(req: Request):
        body = await req.json()
        # Allows partial updates
        _write(body)
        return {"ok": True}
