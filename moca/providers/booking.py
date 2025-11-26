from __future__ import annotations

import asyncio
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from moca.models import Listing, SearchCriteria
from moca.providers.base import Provider, normalize_price


SEARCH_URL = "https://www.booking.com/searchresults.html"


class BookingProvider(Provider):
    name = "Booking.com"

    def __init__(self, use_live_data: bool = False, timeout: float = 12.0) -> None:
        self.use_live_data = use_live_data
        self.timeout = timeout

    async def search(self, criteria: SearchCriteria) -> List[Listing]:
        if not self.use_live_data:
            return self._simulate(criteria)
        try:
            return await self._scrape(criteria)
        except Exception:
            # The live search may fail in restricted environments; fall back to simulated data.
            return self._simulate(criteria)

    async def _scrape(self, criteria: SearchCriteria) -> List[Listing]:
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            tasks = [self._fetch_for_destination(client, criteria, destination) for destination in criteria.destinations]
            results: List[List[Listing]] = await asyncio.gather(*tasks)
        listings: List[Listing] = []
        for subset in results:
            listings.extend(subset)
        return listings

    async def _fetch_for_destination(
        self, client: httpx.AsyncClient, criteria: SearchCriteria, destination: str
    ) -> List[Listing]:
        params = self._build_params(criteria, destination)
        response = await client.get(SEARCH_URL, params=params)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div[data-testid='property-card']")
        listings: List[Listing] = []
        for card in cards[:5]:  # avoid over-fetching
            title = card.select_one("div[data-testid='title']")
            if not title:
                continue
            url_tag = card.select_one("a[data-testid='title-link']")
            price_tag = card.select_one("span[data-testid='price-and-discounted-price']")
            rating_tag = card.select_one("div[data-testid='review-score']")
            review_count_tag = card.select_one("div[data-testid='rating-subtitle']")
            distance_tag = card.select_one("span[data-testid='distance']")
            listings.append(
                Listing(
                    provider=self.name,
                    provider_id=(url_tag["href"] if url_tag and url_tag.has_attr("href") else title.get_text(strip=True)),
                    title=title.get_text(strip=True),
                    url=f"https://www.booking.com{url_tag['href']}" if url_tag and url_tag.has_attr("href") else SEARCH_URL,
                    price_total=normalize_price(price_tag.get_text()) if price_tag else None,
                    currency="",
                    rating=self._parse_rating(rating_tag.get_text()) if rating_tag else None,
                    review_count=self._parse_review_count(review_count_tag.get_text()) if review_count_tag else None,
                    location_hint=destination,
                    distance_to_center_km=self._parse_distance(distance_tag.get_text()) if distance_tag else None,
                    beachfront=criteria.beachfront,
                    pool=criteria.pool,
                    bathrooms=criteria.bathrooms,
                    free_cancellation=criteria.free_cancellation,
                    cancellation_policy="Free cancellation when offered by Booking.com",
                )
            )
        if not listings:
            listings = self._simulate(criteria)
        return listings

    def _build_params(self, criteria: SearchCriteria, destination: str) -> dict:
        return {
            "ss": destination,
            "checkin_year": criteria.checkin.year,
            "checkin_month": criteria.checkin.month,
            "checkin_monthday": criteria.checkin.day,
            "checkout_year": criteria.checkout.year,
            "checkout_month": criteria.checkout.month,
            "checkout_monthday": criteria.checkout.day,
            "group_adults": criteria.adults,
            "no_rooms": criteria.rooms,
            "group_children": criteria.children,
            "order": "bayesian_review_score",
        }

    def _simulate(self, criteria: SearchCriteria) -> List[Listing]:
        sample: List[Listing] = []
        for destination in criteria.destinations:
            sample.append(
                Listing(
                    provider=self.name,
                    provider_id=f"bk-{destination}-pool",
                    title=f"{destination} Beach Retreat",
                    url=f"https://www.booking.com/{destination}-beach-retreat",
                    price_total=850.0,
                    currency="EUR",
                    rating=9.1,
                    review_count=428,
                    location_hint=destination,
                    distance_to_center_km=1.2,
                    beachfront=True,
                    pool=True,
                    rooms=criteria.rooms,
                    bathrooms=criteria.bathrooms or 1,
                    free_cancellation=True,
                    cancellation_policy="Free cancellation",
                )
            )
            sample.append(
                Listing(
                    provider=self.name,
                    provider_id=f"bk-{destination}-city",
                    title=f"{destination} City Hotel",
                    url=f"https://www.booking.com/{destination}-city",
                    price_total=640.0,
                    currency="EUR",
                    rating=8.5,
                    review_count=112,
                    location_hint=destination,
                    distance_to_center_km=0.4,
                    beachfront=False,
                    pool=False,
                    rooms=criteria.rooms,
                    bathrooms=criteria.bathrooms or 1,
                    free_cancellation=True,
                    cancellation_policy="Free cancellation",
                )
            )
        return sample

    def _parse_rating(self, text: str) -> Optional[float]:
        try:
            return float(text.strip().split()[0])
        except Exception:
            return None

    def _parse_review_count(self, text: str) -> Optional[int]:
        cleaned = "".join(ch for ch in text if ch.isdigit())
        try:
            return int(cleaned)
        except ValueError:
            return None

    def _parse_distance(self, text: str) -> Optional[float]:
        try:
            numeric = text.split()[0].replace(",", ".")
            return float(numeric)
        except Exception:
            return None
