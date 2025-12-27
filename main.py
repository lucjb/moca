from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from moca.models import DateFlexibility, Occupancy, Preferences, SearchCriteria, StayWindow
from moca.search import SearchOrchestrator, save_response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily accommodation search")
    parser.add_argument("--config", type=Path, help="Path to a JSON file with search criteria", required=True)
    parser.add_argument("--output", type=Path, help="Path to write JSON results", default=Path("results.json"))
    return parser.parse_args()


def load_criteria(path: Path) -> SearchCriteria:
    data = json.loads(path.read_text())
    stay = StayWindow(
        checkin=date.fromisoformat(data["stay"]["checkin"]),
        checkout=date.fromisoformat(data["stay"]["checkout"]),
        checkin_flex=DateFlexibility(**data["stay"].get("checkin_flex", {})),
        checkout_flex=DateFlexibility(**data["stay"].get("checkout_flex", {})),
    )
    occupancy = Occupancy(**data["occupancy"])
    preferences = Preferences(**data.get("preferences", {}))
    return SearchCriteria(destinations=data["destinations"], stay=stay, occupancy=occupancy, preferences=preferences)


def main():
    args = parse_args()
    criteria = load_criteria(args.config)
    orchestrator = SearchOrchestrator()
    response = orchestrator.run(criteria)
    save_response(response, args.output)
    print(f"Saved {len(response.results)} results to {args.output}")


if __name__ == "__main__":
    main()

