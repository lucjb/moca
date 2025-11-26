from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

from moca.criteria import DateFlexibility, SearchCriteria, StayDates
from moca.manager import SearchManager
from moca.providers.airbnb import AirbnbProvider
from moca.providers.booking import BookingProvider
from moca.providers.mock import MockProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily accommodation search")
    parser.add_argument("config", type=Path, help="Path to YAML/JSON config with search criteria")
    parser.add_argument("--history", type=Path, help="Path to store search history JSON")
    parser.add_argument("--provider", action="append", choices=["booking", "airbnb", "mock"], help="Provider(s) to use")
    parser.add_argument("--use-mock", action="store_true", help="Force using the mock provider")
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if not yaml:
            raise RuntimeError("pyyaml is required to parse YAML configs")
        return yaml.safe_load(text)
    return json.loads(text)


def parse_criteria(data: Dict[str, Any]) -> SearchCriteria:
    stay_info = data["stay"]
    stay = StayDates(
        checkin=_parse_date(stay_info["checkin"]),
        checkout=_parse_date(stay_info["checkout"]),
        checkin_flex=_parse_flex(stay_info.get("checkin_flex")),
        checkout_flex=_parse_flex(stay_info.get("checkout_flex")),
    )
    return SearchCriteria(
        destinations=data["destinations"],
        stay=stay,
        adults=data.get("adults", 2),
        children=data.get("children", 0),
        rooms=data.get("rooms", 1),
        beachfront=data.get("beachfront", False),
        nice_beach=data.get("nice_beach", False),
        close_to_city_center=data.get("close_to_city_center", False),
        max_transfer_from_airport_minutes=data.get("max_transfer_from_airport_minutes"),
        all_inclusive=data.get("all_inclusive", False),
        pool=data.get("pool", False),
        big_room=data.get("big_room", False),
        bathrooms=data.get("bathrooms"),
        lift=data.get("lift", False),
        ground_floor=data.get("ground_floor", False),
        accommodation_type=data.get("accommodation_type"),
        free_cancellation_required=data.get("free_cancellation_required", True),
        currency=data.get("currency", "USD"),
        max_price_per_night=data.get("max_price_per_night"),
    )


def _parse_flex(data: Dict[str, Any] | None) -> DateFlexibility:
    if not data:
        return DateFlexibility()
    return DateFlexibility(
        days_before=data.get("days_before", 0),
        days_after=data.get("days_after", 0),
    )


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def build_providers(names: List[str] | None, use_mock: bool) -> List:
    if use_mock:
        return [MockProvider()]
    names = names or ["booking", "airbnb"]
    mapping = {
        "booking": BookingProvider,
        "airbnb": AirbnbProvider,
        "mock": MockProvider,
    }
    return [mapping[name]() for name in names]


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    criteria = parse_criteria(config)
    providers = build_providers(args.provider, args.use_mock)
    manager = SearchManager(providers, history_path=args.history)
    results = manager.run(criteria)
    print(manager.to_json(results))


if __name__ == "__main__":
    main()
