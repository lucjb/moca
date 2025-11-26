from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from moca.models import SearchCriteria, SearchResult
from moca.providers.base import AccommodationProvider


class BookingProvider(AccommodationProvider):
    name = "booking"

    BASE_URL = "https://www.booking.com/searchresults.html"

    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        for destination in criteria.destinations:
            for checkin_date in self._flex_dates(
                criteria.stay.checkin, criteria.stay.checkin_flex.days_before, criteria.stay.checkin_flex.days_after
            ):
                checkout = checkin_date + (criteria.stay.checkout - criteria.stay.checkin)
                yield from self._search_single_destination(criteria, destination, checkin_date, checkout)

    def _search_single_destination(self, criteria: SearchCriteria, destination: str, checkin: date, checkout: date):
        params = {
            "ss": destination,
            "checkin_year_month_monthday": checkin.strftime("%Y-%m-%d"),
            "checkout_year_month_monthday": checkout.strftime("%Y-%m-%d"),
            "group_adults": criteria.occupancy.adults,
            "group_children": criteria.occupancy.children,
            "no_rooms": criteria.occupancy.rooms,
            "sb_travel_purpose": "leisure",
        }
        response = requests.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for card in soup.select('div[data-testid="property-card"]'):
            title_el = card.select_one('div[data-testid="title"]')
            price_el = card.select_one('span[data-testid="price-and-discounted-price"]')
            rating_el = card.select_one('div[data-testid="review-score"]') or card.select_one('div[data-testid="rating-score"]')
            link_el = card.select_one('a[data-testid="title-link"]')
            if not title_el or not link_el:
                continue
            url = link_el.get("href")
            if url and url.startswith("/"):
                url = f"https://www.booking.com{url}"
            yield SearchResult(
                provider=self.name,
                destination=destination,
                title=title_el.get_text(strip=True),
                url=url or "",
                price=price_el.get_text(" ", strip=True) if price_el else None,
                rating=rating_el.get_text(" ", strip=True) if rating_el else None,
                raw={"checkin": checkin.isoformat(), "checkout": checkout.isoformat()},
            )

    @staticmethod
    def _flex_dates(start: date, days_before: int, days_after: int):
        for offset in range(-days_before, days_after + 1):
            yield start + timedelta(days=offset)

