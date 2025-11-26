from __future__ import annotations

import abc
from typing import Iterable, List

from moca.models import SearchCriteria, SearchResult


class AccommodationProvider(abc.ABC):
    name: str

    @abc.abstractmethod
    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        ...

    def batched_search(self, criteria: SearchCriteria) -> List[SearchResult]:
        return list(self.search(criteria))

