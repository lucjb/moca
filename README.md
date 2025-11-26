# moca

A lightweight prototype that searches for accommodations across multiple providers (Booking.com and Airbnb) using a shared search criteria definition. The workflow is designed for daily runs so you can keep booking cancellable options while checking for improvements.

## Features

- Structured search criteria with date flexibility, occupancy, and amenity preferences.
- Provider adapters for Booking.com (with optional live scraping) and Airbnb (simulated offline-ready feed).
- Simple scoring and ranking that prioritises free cancellation, desired amenities (pool, beachfront, proximity to centre), and review quality.
- YAML-driven configuration so you can define multiple destinations and preferences.
- History stored in `~/.moca/history.json` for quick diffing between daily runs.

## Quick start

1. Create and activate a Python 3.10+ environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example config and edit it to your liking:
   ```bash
   cp search_criteria.example.yaml search_criteria.yaml
   ```
4. Run a simulated search (default avoids live scraping to stay stable offline):
   ```bash
   python -m moca.cli --config search_criteria.yaml
   ```
5. (Optional) Attempt live Booking.com scraping:
   ```bash
   python -m moca.cli --config search_criteria.yaml --live
   ```

The CLI prints the criteria and the top-ranked candidates, and stores each run in `~/.moca/history.json`.

## Extending

- Add more providers by subclassing `moca.providers.base.Provider`.
- Adjust scoring in `moca.ranking.top_candidates` or the `Listing.score` method if you want different weighting.
- Expand the search criteria in `moca.models.SearchCriteria` to capture additional requirements like accessibility or pet policies.

## Caveats

- The Airbnb adapter currently returns simulated data to keep the prototype offline-friendly.
- Live scraping may fail depending on network restrictions and anti-bot protections; the Booking.com provider automatically falls back to simulated results.
