from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from moca.models import SearchCriteria, SearchResult
from moca.providers.base import AccommodationProvider


class AirbnbProvider(AccommodationProvider):
    name = "airbnb"

    BASE_URL = "https://www.airbnb.com/s/{destination}/homes"

    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        for destination in criteria.destinations:
            for checkin_date in self._flex_dates(
                criteria.stay.checkin, criteria.stay.checkin_flex.days_before, criteria.stay.checkin_flex.days_after
            ):
                checkout = checkin_date + (criteria.stay.checkout - criteria.stay.checkin)
                yield from self._search_destination(criteria, destination, checkin_date, checkout)

    def _search_destination(self, criteria: SearchCriteria, destination: str, checkin: date, checkout: date):
        url = self.BASE_URL.format(destination=destination.replace(" ", "-"))
        params = {
            "adults": criteria.occupancy.adults,
            "children": criteria.occupancy.children,
            "checkin": checkin.isoformat(),
            "checkout": checkout.isoformat(),
            "rooms": criteria.occupancy.rooms,
        }
        response = requests.get(url, params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        bootstrap = soup.find("script", string=re.compile("bootstrapData"))
        if bootstrap:
            for item in self._parse_bootstrap_data(bootstrap.string or "", destination, checkin, checkout):
                yield item
        else:
            for card in soup.select("div[data-testid='card-container']"):
                title_el = card.select_one("div[aria-label]")
                url_el = card.find("a", href=True)
                price_el = card.select_one("span[data-testid='price']")
                if not title_el or not url_el:
                    continue
                yield SearchResult(
                    provider=self.name,
                    destination=destination,
                    title=title_el.get_text(strip=True),
                    url=f"https://www.airbnb.com{url_el['href']}",
                    price=price_el.get_text(" ", strip=True) if price_el else None,
                    rating=None,
                    raw={"checkin": checkin.isoformat(), "checkout": checkout.isoformat()},
                )

    @staticmethod
    def _parse_bootstrap_data(script_text: str, destination: str, checkin: date, checkout: date):
        match = re.search(r"bootstrapData\s*=\s*(\{.*\});", script_text)
        if not match:
            return []
        data = json.loads(match.group(1))
        listings = data.get("niobeMinimalClientData", [])
        results = []
        for entry in listings:
            try:
                listing = entry[1]["data"]["presentation"]["stayProductSearchResults"]["results"].get("searchResults", [])
            except Exception:
                continue
            for result in listing:
                listing_info = result.get("listing", {})
                title = listing_info.get("title")
                url = listing_info.get("id")
                price = (
                    result.get("pricingQuote", {})
                    .get("structuredStayDisplayPrice", {})
                    .get("primaryLine", {})
                    .get("price")
                )
                rating = listing_info.get("avgRating")
                if not title or not url:
                    continue
                results.append(
                    SearchResult(
                        provider="airbnb",
                        destination=destination,
                        title=title,
                        url=f"https://www.airbnb.com/rooms/{url}",
                        price=price,
                        rating=str(rating) if rating is not None else None,
                        raw={"checkin": checkin.isoformat(), "checkout": checkout.isoformat()},
                    )
                )
        return results

    @staticmethod
    def _flex_dates(start: date, days_before: int, days_after: int):
        for offset in range(-days_before, days_after + 1):
            yield start + timedelta(days=offset)

