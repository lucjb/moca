# moca

Daily accommodation searcher that can poll well-known platforms (Booking.com and Airbnb) with a rich set of filters and keep a history so you can re-run the search every day until you find a better option.

## Features
- Flexible date window for both check-in and check-out
- Multiple destinations per run
- Preferences like beachfront, pool, all-inclusive, near city center, large rooms, bathrooms, lift/ground-floor hints, and more
- Supports Booking.com and Airbnb via RapidAPI plus a mock provider for local testing
- Ranks results favoring free cancellation so you can swap to better stays as they appear
- Optional JSON history file to track the best options per day

## Quick start
1. Install dependencies (Python 3.11+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. Create a config file (YAML or JSON) describing your trip:
   ```yaml
   destinations:
     - Palma de Mallorca
     - Malaga
   stay:
     checkin: 2024-08-15
     checkout: 2024-08-22
     checkin_flex:
       days_before: 1
       days_after: 1
     checkout_flex:
       days_before: 0
       days_after: 2
   adults: 2
   children: 1
   rooms: 1
   beachfront: true
   pool: true
   all_inclusive: false
   close_to_city_center: true
   bathrooms: 2
   lift: true
   ground_floor: false
   accommodation_type: hotel
   free_cancellation_required: true
   currency: EUR
   max_price_per_night: 300
   ```
3. Export RapidAPI keys (optional but needed for live provider calls):
   ```bash
   export BOOKING_RAPIDAPI_KEY=your_booking_key
   export AIRBNB_RAPIDAPI_KEY=your_airbnb_key
   ```
4. Run the CLI (use `--use-mock` to avoid network calls):
   ```bash
   python -m moca.cli config.yaml --history data/history.json --provider booking --provider airbnb
   ```

The CLI prints ranked JSON results and, when `--history` is provided, appends the run to that file. Schedule the command with cron or a task runner to execute it daily.

## Notes on providers
- **BookingProvider** and **AirbnbProvider** expect RapidAPI credentials. Without keys they safely skip execution so your daily automation won’t fail.
- **MockProvider** returns deterministic results and is handy for testing config parsing, ranking, and storage.

## Development
- Extend `moca/providers` to add more data sources.
- Adjust ranking weights in `moca/ranking.py` to reflect your personal priorities (pool weight, beachfront bonus, price penalties, etc.).
