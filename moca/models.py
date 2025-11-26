from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class Flexibility:
    """Represents how many days around a target date we can shift."""

    days_before: int = 0
    days_after: int = 0


@dataclass
class SearchCriteria:
    destinations: List[str]
    checkin: date
    checkout: date
    checkin_flexibility: Flexibility = field(default_factory=Flexibility)
    checkout_flexibility: Flexibility = field(default_factory=Flexibility)
    adults: int = 2
    children: int = 0
    rooms: int = 1
    beachfront: bool = False
    nice_beach: bool = False
    close_to_center: bool = False
    max_airport_transfer_minutes: Optional[int] = None
    all_inclusive: bool = False
    pool: bool = False
    big_room: bool = False
    bathrooms: Optional[int] = None
    lift: Optional[bool] = None
    ground_floor: Optional[bool] = None
    property_types: Optional[List[str]] = None
    free_cancellation: bool = True

    def describe(self) -> str:
        destination_display = ", ".join(self.destinations)
        return (
            f"Destinations: {destination_display}\n"
            f"Dates: {self.checkin.isoformat()} → {self.checkout.isoformat()}\n"
            f"Flexibility: check-in ±({self.checkin_flexibility.days_before}/{self.checkin_flexibility.days_after}) days, "
            f"check-out ±({self.checkout_flexibility.days_before}/{self.checkout_flexibility.days_after}) days\n"
            f"Guests: {self.adults} adults, {self.children} children across {self.rooms} room(s)\n"
            f"Preferences: beachfront={self.beachfront}, pool={self.pool}, close_to_center={self.close_to_center}, "
            f"all_inclusive={self.all_inclusive}, free_cancellation={self.free_cancellation}"
        )


@dataclass
class Listing:
    provider: str
    provider_id: str
    title: str
    url: str
    price_total: Optional[float]
    currency: str
    rating: Optional[float]
    review_count: Optional[int]
    location_hint: Optional[str]
    distance_to_center_km: Optional[float]
    beachfront: bool = False
    pool: bool = False
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None
    free_cancellation: bool = True
    cancellation_policy: Optional[str] = None

    def score(self, preferences: SearchCriteria) -> float:
        """Compute a simple weighted score against the provided preferences."""

        score = 0.0
        if self.free_cancellation:
            score += 2
        if preferences.pool and self.pool:
            score += 1.5
        if preferences.beachfront and self.beachfront:
            score += 1.5
        if preferences.close_to_center and self.distance_to_center_km is not None:
            score += max(0, 1 - (self.distance_to_center_km / 5))
        if self.rating:
            score += min(self.rating / 10, 1.0)
        if preferences.bathrooms and self.bathrooms:
            if self.bathrooms >= preferences.bathrooms:
                score += 0.5
        if self.price_total:
            score += 1 / (1 + self.price_total / 1000)
        return score


@dataclass
class ProviderResult:
    provider: str
    listings: List[Listing]
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class SearchRun:
    criteria: SearchCriteria
    results: List[ProviderResult]

    def flattened(self) -> List[Listing]:
        items: List[Listing] = []
        for result in self.results:
            items.extend(result.listings)
        return items
