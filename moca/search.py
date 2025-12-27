from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from moca.models import SearchCriteria, SearchResponse
from moca.providers.airbnb import AirbnbProvider
from moca.providers.booking import BookingProvider
from moca.providers.base import AccommodationProvider


class SearchOrchestrator:
    def __init__(self, providers: Iterable[AccommodationProvider] | None = None):
        self.providers = list(providers) if providers is not None else [BookingProvider(), AirbnbProvider()]

    def run(self, criteria: SearchCriteria) -> SearchResponse:
        results: List = []
        for provider in self.providers:
            results.extend(provider.batched_search(criteria))
        return SearchResponse(criteria=criteria, results=results)


def serialize_response(response: SearchResponse) -> Dict:
    return {
        "criteria": {
            "destinations": response.criteria.destinations,
            "stay": {
                "checkin": response.criteria.stay.checkin.isoformat(),
                "checkout": response.criteria.stay.checkout.isoformat(),
                "checkin_flex": response.criteria.stay.checkin_flex.__dict__,
                "checkout_flex": response.criteria.stay.checkout_flex.__dict__,
            },
            "occupancy": response.criteria.occupancy.__dict__,
            "preferences": response.criteria.preferences.__dict__,
        },
        "results": [
            {
                "provider": r.provider,
                "destination": r.destination,
                "title": r.title,
                "url": r.url,
                "price": r.price,
                "rating": r.rating,
                "raw": r.raw,
            }
            for r in response.results
        ],
    }


def save_response(response: SearchResponse, path: Path):
    path.write_text(json.dumps(serialize_response(response), indent=2))

