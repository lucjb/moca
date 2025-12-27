# moca

Daily accommodation search helper for quickly surfacing Booking.com and Airbnb options that match a set of preferences. Provide a JSON config describing your trip and run the CLI to gather the latest listings.

## Quickstart

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy `example_config.json` and edit destinations, dates, and preferences:

```bash
cp example_config.json my_trip.json
```

3. Run the search:

```bash
python main.py --config my_trip.json --output results.json
```

The script will query Booking.com and Airbnb for each destination and flexible date combination. Results are written to the output file, including property titles, links, and any price/rating information that could be parsed.

## Configuration

- `destinations`: List of destination strings (city, region, or point of interest).
- `stay.checkin` / `stay.checkout`: ISO-8601 dates.
- `stay.checkin_flex` and `stay.checkout_flex`: Number of days before/after to shift check-in or check-out when searching.
- `occupancy`: Adults, children, and room count.
- `preferences`: High-level preferences; not every preference is supported by every provider yet, but they are carried through for future filtering/notification logic.

## Notes

- This first version relies on public search pages and lightweight HTML parsing. Providers occasionally change their markup; if you see empty results, re-run with different destinations or inspect the HTML to update selectors.
- Respect provider terms of service and robots.txt before automating large numbers of requests.
- To schedule daily searches, pair this script with cron (e.g. `0 7 * * * /usr/bin/python /path/to/main.py --config /path/to/trip.json --output /tmp/results.json`).

