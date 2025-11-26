from __future__ import annotations

from typing import List

from moca.models import Listing, SearchCriteria


def rank_listings(criteria: SearchCriteria, listings: List[Listing]) -> List[Listing]:
    """Return listings ordered by the scoring function."""

    return sorted(listings, key=lambda listing: listing.score(criteria), reverse=True)


def top_candidates(criteria: SearchCriteria, listings: List[Listing], limit: int = 5) -> List[Listing]:
    return rank_listings(criteria, listings)[:limit]
