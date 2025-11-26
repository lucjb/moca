from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict

from moca.models import SearchRun

DEFAULT_STORAGE = Path.home() / ".moca" / "history.json"


def _ensure_storage_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_history(path: Path = DEFAULT_STORAGE) -> Dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_run(run: SearchRun, path: Path = DEFAULT_STORAGE) -> None:
    _ensure_storage_dir(path)
    payload = load_history(path)
    run_key = datetime.utcnow().isoformat()
    payload[run_key] = {
        "criteria": asdict(run.criteria),
        "results": [
            {
                "provider": result.provider,
                "meta": result.meta,
                "listings": [asdict(listing) for listing in result.listings],
            }
            for result in run.results
        ],
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, default=str)


def load_last_run(path: Path = DEFAULT_STORAGE) -> Dict:
    history = load_history(path)
    if not history:
        return {}
    latest_key = sorted(history.keys())[-1]
    return {"timestamp": latest_key, "data": history[latest_key]}
