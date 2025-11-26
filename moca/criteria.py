from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class DateFlexibility:
    """Represents flexible ranges around a target date."""

    days_before: int = 0
    days_after: int = 0


@dataclass
class StayDates:
    checkin: date
    checkout: date
    checkin_flex: DateFlexibility = field(default_factory=DateFlexibility)
    checkout_flex: DateFlexibility = field(default_factory=DateFlexibility)


@dataclass
class SearchCriteria:
    destinations: List[str]
    stay: StayDates
    adults: int
    children: int = 0
    rooms: int = 1
    beachfront: bool = False
    nice_beach: bool = False
    close_to_city_center: bool = False
    max_transfer_from_airport_minutes: Optional[int] = None
    all_inclusive: bool = False
    pool: bool = False
    big_room: bool = False
    bathrooms: Optional[int] = None
    lift: bool = False
    ground_floor: bool = False
    accommodation_type: Optional[str] = None  # "hotel", "house", None
    free_cancellation_required: bool = True
    currency: str = "USD"
    max_price_per_night: Optional[float] = None


__all__ = ["DateFlexibility", "StayDates", "SearchCriteria"]
