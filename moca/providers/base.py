from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from moca.criteria import SearchCriteria
from moca.providers.models import SearchResult


class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        """Perform a search for the given criteria."""


__all__ = ["SearchProvider"]
