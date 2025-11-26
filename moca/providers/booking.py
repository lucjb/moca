from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from moca.models import SearchCriteria, SearchResult
from moca.providers.base import AccommodationProvider

logger = logging.getLogger(__name__)


class BookingProvider(AccommodationProvider):
    name = "booking"

    BASE_URL = "https://www.booking.com/searchresults.html"

    # Headers to mimic a real browser request
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def search(self, criteria: SearchCriteria) -> Iterable[SearchResult]:
        for destination in criteria.destinations:
            for checkin_date in self._flex_dates(
                criteria.stay.checkin, criteria.stay.checkin_flex.days_before, criteria.stay.checkin_flex.days_after
            ):
                checkout = checkin_date + (criteria.stay.checkout - criteria.stay.checkin)
                yield from self._search_single_destination(criteria, destination, checkin_date, checkout)

    def _search_single_destination(self, criteria: SearchCriteria, destination: str, checkin: date, checkout: date):
        # Booking.com uses specific date format: YYYY-MM-DD
        params = {
            "ss": destination,
            "checkin": checkin.strftime("%Y-%m-%d"),
            "checkout": checkout.strftime("%Y-%m-%d"),
            "group_adults": str(criteria.occupancy.adults),
            "group_children": str(criteria.occupancy.children),
            "no_rooms": str(criteria.occupancy.rooms),
            "sb_travel_purpose": "leisure",
        }

        # Add preferences if specified
        if criteria.preferences.free_cancellation:
            params["nflt"] = "1"  # Free cancellation filter

        # Note: Booking.com property type filtering via URL params is complex.
        # We'll filter results client-side based on URL path and title.

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                headers=self.HEADERS,
                timeout=30,
                allow_redirects=True,
            )
            response.raise_for_status()

            # Check if we got redirected to a different page (might indicate blocking)
            if "searchresults" not in response.url.lower():
                logger.warning(f"Unexpected redirect for {destination}: {response.url}")
                return

            # Handle encoding properly - try to detect from content or default to utf-8
            try:
                # Try to detect encoding from response headers or content
                if response.encoding:
                    response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
                else:
                    response.encoding = 'utf-8'
                html_content = response.text
            except (UnicodeDecodeError, LookupError):
                # Fallback: decode as utf-8 with error handling
                html_content = response.content.decode('utf-8', errors='replace')

            soup = BeautifulSoup(html_content, "html.parser")

            # Try multiple selector patterns as Booking.com may use different structures
            property_cards = (
                soup.select('div[data-testid="property-card"]')
                or soup.select('div[data-testid="property-card-container"]')
                or soup.select('div.c-sr_property-card')
                or soup.select('div.sr_item')
            )

            if not property_cards:
                # Check if this might be a blocking/error page
                if len(response.text) < 10000 or "captcha" in response.text.lower() or "blocked" in response.text.lower():
                    logger.warning(f"Possible blocking or error page for {destination} (checkin: {checkin}, checkout: {checkout})")
                else:
                    logger.debug(f"No property cards found for {destination} (checkin: {checkin}, checkout: {checkout}). Response length: {len(response.text)}")
                return

            logger.info(f"Found {len(property_cards)} properties for {destination}")

            for card in property_cards:
                try:
                    # Try multiple selector patterns for title
                    title_el = (
                        card.select_one('div[data-testid="title"]')
                        or card.select_one('h3[data-testid="title"]')
                        or card.select_one('a[data-testid="title-link"]')
                        or card.select_one('a.sr-hotel__name')
                        or card.select_one('span.sr-hotel__name')
                    )

                    # Try multiple selector patterns for link
                    link_el = (
                        card.select_one('a[data-testid="title-link"]')
                        or card.select_one('a.sr-hotel__name')
                        or card.select_one('a[href*="/hotel/"]')
                        or card.find("a", href=True)
                    )

                    if not title_el or not link_el:
                        continue

                    title = title_el.get_text(strip=True, separator=" ")
                    if not title:
                        continue

                    url = link_el.get("href", "")
                    if url:
                        if url.startswith("/"):
                            url = urljoin("https://www.booking.com", url)
                        elif not url.startswith("http"):
                            url = urljoin("https://www.booking.com", "/" + url.lstrip("/"))

                    # Try multiple selector patterns for price
                    price_el = (
                        card.select_one('span[data-testid="price-and-discounted-price"]')
                        or card.select_one('div[data-testid="price-and-discounted-price"]')
                        or card.select_one('span.bui-price-display__value')
                        or card.select_one('div.bui-price-display__value')
                        or card.select_one('strong.price')
                    )

                    # Try multiple selector patterns for rating
                    rating_el = (
                        card.select_one('div[data-testid="review-score"]')
                        or card.select_one('div[data-testid="rating-score"]')
                        or card.select_one('div.bui-review-score__badge')
                        or card.select_one('div.sr-review-score')
                    )

                    price = None
                    if price_el:
                        price_text = price_el.get_text(strip=True, separator=" ")
                        if price_text:
                            price = " ".join(price_text.split())

                    rating = None
                    if rating_el:
                        rating_text = rating_el.get_text(strip=True, separator=" ")
                        if rating_text:
                            rating = " ".join(rating_text.split())

                    # Filter by property type if specified
                    if criteria.preferences.property_type:
                        property_type = self._extract_property_type(url, title)
                        requested_type = criteria.preferences.property_type.lower()
                        # Only exclude if we can determine the type and it doesn't match
                        # If we can't determine the type, include it (to avoid false negatives)
                        if property_type is not None and not self._matches_property_type(property_type, requested_type):
                            continue

                    yield SearchResult(
                        provider=self.name,
                        destination=destination,
                        title=title,
                        url=url,
                        price=price,
                        rating=rating,
                        raw={
                            "checkin": checkin.isoformat(),
                            "checkout": checkout.isoformat(),
                            "search_url": response.url,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Error parsing property card: {e}")
                    continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {destination}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for {destination}: {e}")

    @staticmethod
    def _extract_property_type(url: str, title: str) -> str | None:
        """Extract property type from URL path and title.
        
        Note: Booking.com URLs often contain /hotel/ even for non-hotel properties,
        so we prioritize title-based detection over URL-based detection.
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # First, check title for property type keywords (more reliable)
        # Check for non-hotel types first to avoid false positives
        if "villa" in title_lower and "hotel" not in title_lower:
            return "villa"
        elif "apartment" in title_lower or "apartamento" in title_lower:
            return "apartment"
        elif "hostel" in title_lower:
            return "hostel"
        elif "guesthouse" in title_lower or "guest house" in title_lower:
            return "guesthouse"
        elif "bed and breakfast" in title_lower or "b&b" in title_lower:
            return "bed and breakfast"
        elif "aparthotel" in title_lower or "apart-hotel" in title_lower:
            return "aparthotel"
        elif "resort" in title_lower:
            # Resorts are typically hotels, but can be standalone resorts
            # For filtering purposes, treat as hotel if "hotel" is requested
            return "resort"
        elif "hotel" in title_lower:
            return "hotel"
        elif "suite" in title_lower and "hotel" not in title_lower:
            # Suites are often apartments or hotel rooms, but if no hotel mention, likely apartment
            return "apartment"

        # Fallback: Check URL path for property type indicators
        # Only use URL if title didn't give us a clear indication
        if "/apartment/" in url_lower:
            return "apartment"
        elif "/villa/" in url_lower:
            return "villa"
        elif "/resort/" in url_lower:
            return "resort"
        elif "/hostel/" in url_lower:
            return "hostel"
        elif "/guesthouse/" in url_lower or "/guest-house/" in url_lower:
            return "guesthouse"
        elif "/bed-and-breakfast/" in url_lower or "/b&b/" in url_lower:
            return "bed and breakfast"
        elif "/aparthotel/" in url_lower:
            return "aparthotel"
        elif "/hotel/" in url_lower:
            # This is the default, but less reliable since many properties use /hotel/ in URL
            return "hotel"

        return None

    @staticmethod
    def _matches_property_type(extracted_type: str | None, requested_type: str) -> bool:
        """Check if extracted property type matches the requested type."""
        if not extracted_type:
            # If we can't determine the type, include it (to avoid false negatives)
            # This is conservative - we'd rather include some false positives than miss valid results
            return True

        extracted_lower = extracted_type.lower()
        requested_lower = requested_type.lower()

        # Direct match
        if extracted_lower == requested_lower:
            return True

        # Handle common variations and aliases
        type_mappings = {
            "hotel": ["hotel", "hotels"],
            "apartment": ["apartment", "apartments", "apartamento", "apartamentos"],
            "villa": ["villa", "villas"],
            "resort": ["resort", "resorts"],
            "hostel": ["hostel", "hostels"],
            "guesthouse": ["guesthouse", "guest house", "guest-house", "guesthouses"],
            "bed and breakfast": ["bed and breakfast", "b&b", "b and b", "bed & breakfast"],
            "aparthotel": ["aparthotel", "apart-hotel", "apart hotel"],
        }

        # Special case: resorts are often considered hotels for filtering purposes
        if requested_lower in ["hotel", "hotels"] and extracted_lower == "resort":
            return True

        # Check if requested type matches any of the mapped types
        for key, aliases in type_mappings.items():
            if requested_lower in aliases:
                if extracted_lower == key or extracted_lower in aliases:
                    return True

        return False

    @staticmethod
    def _flex_dates(start: date, days_before: int, days_after: int):
        for offset in range(-days_before, days_after + 1):
            yield start + timedelta(days=offset)

