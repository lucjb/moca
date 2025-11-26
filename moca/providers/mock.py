from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from moca.criteria import SearchCriteria
from moca.providers.base import SearchProvider
from moca.providers.models import SearchResult


class MockProvider(SearchProvider):
    """Static provider useful for demos and unit tests."""

    name = "mock"

    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        results: List[SearchResult] = []
        for destination in criteria.destinations:
            results.append(
                SearchResult(
                    provider=self.name,
                    listing_id=f"{destination}-pool",
                    name=f"Demo Pool Stay in {destination}",
                    destination=destination,
                    url="https://example.com/pool",
                    price_per_night=210.0,
                    currency=criteria.currency,
                    rating=9.1,
                    review_count=120,
                    free_cancellation=True,
                    pool=True,
                    beachfront=criteria.beachfront,
                    all_inclusive=criteria.all_inclusive,
                    distance_to_center_km=0.9,
                    bedrooms=2,
                    bathrooms=2,
                    has_lift=True,
                    floor=criteria.ground_floor and 0 or 3,
                    is_hotel=True,
                    metadata={},
                    fetched_at=datetime.utcnow(),
                )
            )
            results.append(
                SearchResult(
                    provider=self.name,
                    listing_id=f"{destination}-budget",
                    name=f"Budget Stay in {destination}",
                    destination=destination,
                    url="https://example.com/budget",
                    price_per_night=120.0,
                    currency=criteria.currency,
                    rating=8.4,
                    review_count=80,
                    free_cancellation=True,
                    pool=False,
                    beachfront=False,
                    all_inclusive=False,
                    distance_to_center_km=0.3,
                    bedrooms=1,
                    bathrooms=1,
                    has_lift=True,
                    floor=2,
                    is_hotel=False,
                    metadata={},
                    fetched_at=datetime.utcnow(),
                )
            )
        return results


__all__ = ["MockProvider"]
