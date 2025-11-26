from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Sequence

from moca.criteria import SearchCriteria
from moca.providers.base import SearchProvider
from moca.providers.models import SearchResult
from moca.ranking import rank_results
from moca.storage import HistoryStorage

LOGGER = logging.getLogger(__name__)


class SearchManager:
    def __init__(
        self,
        providers: Sequence[SearchProvider],
        history_path: Path | None = None,
    ) -> None:
        self.providers = providers
        self.history = HistoryStorage(history_path) if history_path else None

    def run(self, criteria: SearchCriteria) -> List[SearchResult]:
        aggregated: List[SearchResult] = []
        for provider in self.providers:
            LOGGER.info("Running search with provider %s", provider.name)
            aggregated.extend(provider.search(criteria))
        ranked = rank_results(criteria, aggregated)
        LOGGER.info("Collected %s results", len(ranked))
        if self.history:
            self.history.save(criteria, ranked)
        return ranked

    def to_json(self, results: Iterable[SearchResult]) -> str:
        serializable = [asdict(item) for item in results]
        return json.dumps(serializable, default=str, indent=2)


__all__ = ["SearchManager"]
