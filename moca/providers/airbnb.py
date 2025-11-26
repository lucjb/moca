from __future__ import annotations

from typing import List

from moca.models import Listing, SearchCriteria
from moca.providers.base import Provider


class AirbnbProvider(Provider):
    name = "Airbnb"

    def __init__(self, use_live_data: bool = False) -> None:
        # Airbnb search requires heavier scraping or the official API. For now we default to
        # simulated listings while keeping the public interface identical to other providers.
        self.use_live_data = use_live_data

    async def search(self, criteria: SearchCriteria) -> List[Listing]:
        # A real implementation could use the Airbnb public search API with an API key or
        # a headless browser scraper. We keep the placeholder small so the workflow can run
        # offline for experimentation.
        return self._simulate(criteria)

    def _simulate(self, criteria: SearchCriteria) -> List[Listing]:
        results: List[Listing] = []
        for destination in criteria.destinations:
            results.append(
                Listing(
                    provider=self.name,
                    provider_id=f"ab-{destination}-villa",
                    title=f"Spacious villa in {destination}",
                    url=f"https://www.airbnb.com/rooms/{destination}-villa",
                    price_total=990.0,
                    currency="EUR",
                    rating=4.92,
                    review_count=321,
                    location_hint=destination,
                    distance_to_center_km=3.4,
                    beachfront=criteria.beachfront,
                    pool=True,
                    rooms=3,
                    bathrooms=2,
                    free_cancellation=criteria.free_cancellation,
                    cancellation_policy="Airbnb moderate (simulated)",
                )
            )
            results.append(
                Listing(
                    provider=self.name,
                    provider_id=f"ab-{destination}-studio",
                    title=f"Central studio in {destination}",
                    url=f"https://www.airbnb.com/rooms/{destination}-studio",
                    price_total=420.0,
                    currency="EUR",
                    rating=4.7,
                    review_count=198,
                    location_hint=destination,
                    distance_to_center_km=0.2,
                    beachfront=False,
                    pool=False,
                    rooms=1,
                    bathrooms=1,
                    free_cancellation=criteria.free_cancellation,
                    cancellation_policy="Airbnb flexible (simulated)",
                )
            )
        return results
