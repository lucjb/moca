from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Iterable, List, Optional

import requests

from moca.criteria import SearchCriteria
from moca.providers.base import SearchProvider
from moca.providers.models import SearchResult

LOGGER = logging.getLogger(__name__)


class AirbnbProvider(SearchProvider):
    """Adapter for the airbnb RapidAPI (airbnb13) search endpoint."""

    name = "airbnb"

    def __init__(self, api_key: Optional[str] = None, host: str = "airbnb13.p.rapidapi.com"):
        self.api_key = api_key or os.getenv("AIRBNB_RAPIDAPI_KEY")
        self.host = host or os.getenv("AIRBNB_RAPIDAPI_HOST", host)

    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        if not self.api_key:
            LOGGER.warning("AirbnbProvider skipped because AIRBNB_RAPIDAPI_KEY is not set")
            return []

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.host,
        }
        results: List[SearchResult] = []
        for destination in criteria.destinations:
            params = self._build_params(criteria, destination)
            response = requests.get(
                f"https://{self.host}/search/{criteria.stay.checkin.isoformat()}/{criteria.stay.checkout.isoformat()}",
                headers=headers,
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json() or {}
            for item in payload.get("results", []):
                results.append(self._map_item(item, destination, criteria.currency))
        return results

    def _build_params(self, criteria: SearchCriteria, destination: str) -> dict:
        return {
            "location": destination,
            "adults": criteria.adults,
            "children": criteria.children,
            "rooms": criteria.rooms,
            "currency": criteria.currency,
            "page": 1,
        }

    def _map_item(self, item: dict, destination: str, currency: str) -> SearchResult:
        pricing = item.get("price", {}) or {}
        return SearchResult(
            provider=self.name,
            listing_id=str(item.get("id")),
            name=item.get("name", "Unknown"),
            destination=destination,
            url=item.get("url", ""),
            price_per_night=pricing.get("rate", {}).get("amount") if pricing.get("rate") else pricing.get("total")
            if pricing
            else None,
            currency=pricing.get("rate", {}).get("currency") or currency,
            rating=item.get("rating"),
            review_count=item.get("reviewsCount"),
            free_cancellation=item.get("cancelPolicy", "").lower() == "flexible",
            pool="pool" in item.get("tags", []),
            beachfront="beachfront" in item.get("tags", []),
            all_inclusive=False,
            bedrooms=item.get("bedrooms"),
            bathrooms=item.get("bathrooms"),
            has_lift=None,
            floor=None,
            is_hotel=False,
            metadata={"tier": item.get("tier")},
            fetched_at=datetime.utcnow(),
        )


__all__ = ["AirbnbProvider"]
