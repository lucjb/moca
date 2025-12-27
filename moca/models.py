from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class DateFlexibility:
    days_before: int = 0
    days_after: int = 0

    def offsets(self) -> List[int]:
        return list(range(-self.days_before, self.days_after + 1))


@dataclass
class StayWindow:
    checkin: date
    checkout: date
    checkin_flex: DateFlexibility = field(default_factory=DateFlexibility)
    checkout_flex: DateFlexibility = field(default_factory=DateFlexibility)


@dataclass
class Occupancy:
    adults: int
    children: int = 0
    rooms: int = 1


@dataclass
class Preferences:
    beachfront: bool = False
    nice_beach: bool = False
    close_to_center_minutes: Optional[int] = None
    max_transfer_minutes: Optional[int] = None
    all_inclusive: bool = False
    pool: bool = False
    large_room: bool = False
    bathrooms: Optional[int] = None
    lift: bool = False
    ground_floor: bool = False
    property_type: Optional[str] = None
    free_cancellation: bool = True


@dataclass
class SearchCriteria:
    destinations: List[str]
    stay: StayWindow
    occupancy: Occupancy
    preferences: Preferences = field(default_factory=Preferences)


@dataclass
class SearchResult:
    provider: str
    destination: str
    title: str
    url: str
    price: Optional[str]
    rating: Optional[str]
    raw: dict


@dataclass
class SearchResponse:
    criteria: SearchCriteria
    results: List[SearchResult]

