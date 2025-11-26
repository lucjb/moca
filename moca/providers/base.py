from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from moca.models import Listing, SearchCriteria


class Provider(ABC):
    name: str

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> List[Listing]:
        """Search listings for the given criteria."""


def normalize_price(raw_price: str) -> float:
    cleaned = "".join(ch for ch in raw_price if ch.isdigit() or ch == "." or ch == ",")
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
