from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class SearchResult:
    provider: str
    listing_id: str
    name: str
    destination: str
    url: str
    price_per_night: Optional[float]
    currency: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    free_cancellation: bool = False
    pool: bool = False
    beachfront: bool = False
    all_inclusive: bool = False
    distance_to_center_km: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    has_lift: Optional[bool] = None
    floor: Optional[int] = None
    is_hotel: Optional[bool] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.utcnow)


__all__ = ["SearchResult"]
