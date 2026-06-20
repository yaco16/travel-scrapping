# Travel Scrapping

FastAPI + HTMX dashboard for very cheap round-trip flight deals from Nice (NCE).

Defaults: one adult, personal item only, no checked/cabin bag, 3-5 nights, under 100 EUR total, from today to 2026-08-30, max 5h air time per direction, max 3h layover, no overnight airport stay.

## Setup

```bash
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with available keys. Keep `.env` untracked.

`API_NINJAS_API_KEY` is optional. When set, airport IATA codes are enriched through API Ninjas Airports API and cached locally. Without it, the app keeps using local French city fallback and never fails startup.

## Dashboard

```bash
.venv/bin/python -m uvicorn travel_scrapping.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## CLI

```bash
.venv/bin/python -m travel_scrapping.cli config
.venv/bin/python -m travel_scrapping.cli search
.venv/bin/python -m travel_scrapping.cli top
.venv/bin/python -m travel_scrapping.cli airports-refresh
.venv/bin/python -m travel_scrapping.cli airports-refresh --iata VCE
.venv/bin/python -m travel_scrapping.cli sqlite-diagnostics
.venv/bin/python -m travel_scrapping.cli search --send-email
```

## Vérifier SQLite

```bash
.venv/bin/python -m travel_scrapping.cli sqlite-diagnostics
sqlite3 data/travel_scrapping.db "select count(*) from search_runs;"
sqlite3 data/travel_scrapping.db "select count(*) from price_observations;"
sqlite3 data/travel_scrapping.db "select observed_at, run_id, source, origin_iata, destination_iata, departure_date, return_date, nights, price, currency, airline from price_observations order by id desc limit 20;"
sqlite3 data/travel_scrapping.db "select origin_iata, destination_iata, departure_date, return_date, nights, min(price), max(price), count(*) from price_observations group by origin_iata, destination_iata, departure_date, return_date, nights having count(*) > 1;"
```

Dashboard: `http://127.0.0.1:8000/sqlite`.

Airport metadata is cached in SQLite table `airport_metadata` with IATA, city, French display city, airport name, country, timezone, coordinates, source, fetch timestamp and raw payload. `airports-refresh --force` bypasses cache and refreshes from API when `API_NINJAS_API_KEY` exists.

## Tests

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov --cov-report=term-missing
```

## Providers

SerpAPI Google Flights is the main live source when `SERPAPI_API_KEY` exists. Travelpayouts widens discovery and is marked medium/low confidence, especially without marker/deeplink support. Playwright is a safe disabled skeleton: no CAPTCHA bypass, no login bypass, no proxy rotation, no rate-limit evasion.

Missing provider keys skip providers instead of crashing.

API Ninjas Airports enriches airport metadata when `API_NINJAS_API_KEY` exists. The key is not required; missing key falls back to local mappings such as `VCE -> Venise`, `SVQ -> Séville`, `BCN -> Barcelone`.

## Email

Brevo transactional email API is optional. `EMAIL_ENABLED=false` hides email actions. If enabled, `BREVO_API_KEY` and `EMAIL_FROM` are required.

## Confidence

High: payload has price, destination, core dates. Medium/low: cached, indicative, or incomplete fields. Unknown layovers/connections lower certainty but do not reject alone.

## Limits

Prices can change or disappear. Booking links must be verified before purchase. Visa status is not guaranteed; unknown is safer than blocking.
