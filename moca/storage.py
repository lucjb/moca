from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

from moca.criteria import SearchCriteria
from moca.providers.models import SearchResult


class HistoryStorage:
    """Simple JSON-based persistence for daily runs."""

    def __init__(self, path: Path | None):
        self.path = path

    def save(self, criteria: SearchCriteria, results: Iterable[SearchResult]) -> None:
        if not self.path:
            return
        history = self._load_all()
        entry = {
            "criteria": asdict(criteria),
            "results": [asdict(r) for r in results],
        }
        history.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fp:
            json.dump(history, fp, default=str, indent=2)

    def _load_all(self) -> List[dict]:
        if not self.path or not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fp:
            return json.load(fp)


__all__ = ["HistoryStorage"]
