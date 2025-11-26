from __future__ import annotations

from typing import Iterable, List

from moca.criteria import SearchCriteria
from moca.providers.models import SearchResult


def score_result(criteria: SearchCriteria, result: SearchResult) -> float:
    score = 0.0
    if result.rating:
        score += result.rating * 2
    if result.free_cancellation:
        score += 30
    if criteria.pool and result.pool:
        score += 8
    if criteria.beachfront and result.beachfront:
        score += 10
    if criteria.all_inclusive and result.all_inclusive:
        score += 6
    if criteria.close_to_city_center and result.distance_to_center_km is not None:
        score += max(0, 5 - result.distance_to_center_km)
    if criteria.bathrooms and result.bathrooms is not None:
        score += min(result.bathrooms, criteria.bathrooms) * 2
    if criteria.big_room and result.bedrooms:
        score += result.bedrooms
    if criteria.max_price_per_night and result.price_per_night:
        price_penalty = max(0, result.price_per_night - criteria.max_price_per_night)
        score -= price_penalty * 0.1
    return score


def rank_results(criteria: SearchCriteria, results: Iterable[SearchResult]) -> List[SearchResult]:
    return sorted(results, key=lambda r: score_result(criteria, r), reverse=True)


__all__ = ["rank_results", "score_result"]
