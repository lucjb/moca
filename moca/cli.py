from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from moca.models import Flexibility, ProviderResult, SearchCriteria, SearchRun
from moca.providers.airbnb import AirbnbProvider
from moca.providers.booking import BookingProvider
from moca.ranking import top_candidates
from moca.storage import load_last_run, save_run


def parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def build_criteria_from_dict(payload: Dict[str, Any]) -> SearchCriteria:
    return SearchCriteria(
        destinations=payload["destinations"],
        checkin=parse_date(payload["checkin"]),
        checkout=parse_date(payload["checkout"]),
        checkin_flexibility=Flexibility(**payload.get("checkin_flexibility", {})),
        checkout_flexibility=Flexibility(**payload.get("checkout_flexibility", {})),
        adults=payload.get("adults", 2),
        children=payload.get("children", 0),
        rooms=payload.get("rooms", 1),
        beachfront=payload.get("beachfront", False),
        nice_beach=payload.get("nice_beach", False),
        close_to_center=payload.get("close_to_center", False),
        max_airport_transfer_minutes=payload.get("max_airport_transfer_minutes"),
        all_inclusive=payload.get("all_inclusive", False),
        pool=payload.get("pool", False),
        big_room=payload.get("big_room", False),
        bathrooms=payload.get("bathrooms"),
        lift=payload.get("lift"),
        ground_floor=payload.get("ground_floor"),
        property_types=payload.get("property_types"),
        free_cancellation=payload.get("free_cancellation", True),
    )


def load_criteria(path: Path) -> List[SearchCriteria]:
    data = yaml.safe_load(path.read_text())
    return [build_criteria_from_dict(item) for item in data.get("searches", [])]


def format_listing(listing) -> str:
    price_display = f"{listing.price_total} {listing.currency}" if listing.price_total else "unknown price"
    return (
        f"[{listing.provider}] {listing.title} — {price_display} | rating: {listing.rating} | "
        f"cancellation: {listing.cancellation_policy} | url: {listing.url}"
    )


async def run_once(config: Path, live: bool = False) -> SearchRun:
    criteria_set = load_criteria(config)
    providers = [BookingProvider(use_live_data=live), AirbnbProvider(use_live_data=live)]

    provider_results: List[ProviderResult] = []
    for provider in providers:
        aggregated_listings = []
        for criteria in criteria_set:
            listings = await provider.search(criteria)
            aggregated_listings.extend(listings)
        provider_results.append(ProviderResult(provider=provider.name, listings=aggregated_listings, meta={"live": str(live)}))

    search_run = SearchRun(criteria=criteria_set[0], results=provider_results)
    save_run(search_run)
    return search_run


def display_results(run: SearchRun) -> None:
    print("Search criteria:")
    print(run.criteria.describe())
    all_listings = run.flattened()
    print("\nTop candidates:")
    for listing in top_candidates(run.criteria, all_listings, limit=5):
        print(" -", format_listing(listing))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the accommodation discovery workflow")
    parser.add_argument("--config", type=Path, default=Path("search_criteria.example.yaml"))
    parser.add_argument("--live", action="store_true", help="Attempt live scraping where supported")
    args = parser.parse_args()

    search_run = await run_once(args.config, live=args.live)
    display_results(search_run)
    last = load_last_run()
    if last:
        print(f"\nLast run stored at {last['timestamp']} with {len(last['data']['results'])} provider entries.")


if __name__ == "__main__":
    asyncio.run(main())
