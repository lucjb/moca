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


class BookingProvider(SearchProvider):
    """Thin wrapper around the booking.com RapidAPI endpoints.

    The provider is intentionally conservative: if credentials are missing it
    simply returns an empty list instead of failing the whole run. This makes it
    possible to run the daily job without leaking secrets into CI environments.
    """

    name = "booking"

    def __init__(self, api_key: Optional[str] = None, host: str = "booking-com.p.rapidapi.com"):
        self.api_key = api_key or os.getenv("BOOKING_RAPIDAPI_KEY")
        self.host = host or os.getenv("BOOKING_RAPIDAPI_HOST", host)

    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        if not self.api_key:
            LOGGER.warning("BookingProvider skipped because BOOKING_RAPIDAPI_KEY is not set")
            return []

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.host,
        }
        results: List[SearchResult] = []
        for destination in criteria.destinations:
            dest_id = self._resolve_destination(destination, headers)
            if not dest_id:
                continue
            params = self._build_search_params(criteria, dest_id)
            response = requests.get(
                f"https://{self.host}/v1/hotels/search",
                headers=headers,
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("result", []):
                results.append(self._map_item(item, destination, criteria.currency))
        return results

    def _resolve_destination(self, destination: str, headers: dict) -> Optional[str]:
        response = requests.get(
            f"https://{self.host}/v1/hotels/locations",
            headers=headers,
            params={"name": destination, "locale": "en-us"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            LOGGER.info("No booking.com destination found for %s", destination)
            return None
        return data[0].get("dest_id")

    def _build_search_params(self, criteria: SearchCriteria, dest_id: str) -> dict:
        stay = criteria.stay
        return {
            "checkout_date": stay.checkout.isoformat(),
            "checkin_date": stay.checkin.isoformat(),
            "dest_id": dest_id,
            "dest_type": "city",
            "locale": "en-us",
            "adults_number": criteria.adults,
            "children_number": criteria.children,
            "room_number": criteria.rooms,
            "order_by": "price",
            "units": "metric",
            "filter_by_currency": criteria.currency,
            "include_adjacency": "true",
            "page_number": 0,
        }

    def _map_item(self, item: dict, destination: str, currency: str) -> SearchResult:
        return SearchResult(
            provider=self.name,
            listing_id=str(item.get("id")),
            name=item.get("hotel_name", "Unknown"),
            destination=destination,
            url=item.get("url", ""),
            price_per_night=item.get("min_total_price"),
            currency=currency,
            rating=item.get("review_score") if item.get("review_score") else None,
            review_count=item.get("review_nr") if item.get("review_nr") else None,
            free_cancellation=item.get("is_free_cancellable") is True,
            pool="pool" in {tag.get("name") for tag in item.get("class_is_default", [])}
            if isinstance(item.get("class_is_default"), list)
            else False,
            beachfront=item.get("is_beach_front"),
            distance_to_center_km=float(item.get("distance_to_cc")) if item.get("distance_to_cc") else None,
            all_inclusive="all inclusive" in str(item).lower(),
            metadata={"raw": "booking"},
            fetched_at=datetime.utcnow(),
        )


__all__ = ["BookingProvider"]
