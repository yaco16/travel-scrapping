# Travel Scrapping

FastAPI + HTMX dashboard for very cheap actionable flight and bus deals from Nice (NCE).

Defaults: one adult, personal item only, no checked/cabin bag, 3-5 nights, under 100 EUR total, from today to 2026-08-30, max 5h air time per direction, max 3h layover, no overnight airport stay.

## Setup

```bash
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with available keys. Keep `.env` untracked.

Amadeus is not used: no `AMADEUS_CLIENT_ID`, no `AMADEUS_CLIENT_SECRET`, no Amadeus resolver or dependency.

Airport resolution uses local SQLite cache first, then local OurAirports data, then API Ninjas as optional fallback, then minimal hardcoded fallback. `OURAIRPORTS_ENABLED=true` is recommended. `API_NINJAS_API_KEY` is optional and kept only as fallback.

`SERPAPI_API_KEY` is required for actionable flight results. `RAPIDAPI_KEY` is required for FlixBus via RapidAPI. `TRAVELPAYOUTS_MARKER` is optional, but without marker Travelpayouts is excluded from main results unless `--include-indicative` is explicit.

## Dashboard

```bash
.venv/bin/python -m uvicorn travel_scrapping.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## CLI

```bash
.venv/bin/python -m travel_scrapping.cli config
.venv/bin/python -m travel_scrapping.cli search
.venv/bin/python -m travel_scrapping.cli search --origin NCE --depart-from 2026-07-01 --depart-to 2026-08-31 --min-nights 3 --max-nights 5 --modes flight,bus
.venv/bin/python -m travel_scrapping.cli top
.venv/bin/python -m travel_scrapping.cli airports-import-ourairports
.venv/bin/python -m travel_scrapping.cli airports-import-ourairports --force-refresh
.venv/bin/python -m travel_scrapping.cli airports-refresh
.venv/bin/python -m travel_scrapping.cli airports-refresh --iata VCE
.venv/bin/python -m travel_scrapping.cli airports-diagnostics
.venv/bin/python -m travel_scrapping.cli serpapi-smoke --origin NCE --destination VCE --depart 2026-07-30 --return 2026-08-02 --debug
.venv/bin/python -m travel_scrapping.cli bus-stations-search --query "Nice"
.venv/bin/python -m travel_scrapping.cli flixbus-smoke --origin "Nice" --destination "Venise" --depart 2026-07-30 --return 2026-08-02 --debug
.venv/bin/python -m travel_scrapping.cli sqlite-diagnostics
.venv/bin/python -m travel_scrapping.cli sqlite-clean-invalid --dry-run
.venv/bin/python -m travel_scrapping.cli sqlite-clean-invalid --execute
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

`sqlite-clean-invalid` sert uniquement au nettoyage des anciennes lignes corrompues de développement local dans `price_observations`. `--dry-run` affiche le nombre de lignes supprimables. `--execute` supprime seulement les observations dont un champ indispensable est nul. Les campagnes ne sont jamais supprimées.

Airport metadata is cached in SQLite table `airport_metadata`. OurAirports is imported into `ourairports_airports` from `data/sources/ourairports/airports.csv`.

## Tests

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov --cov-report=term-missing
```

## Providers

SerpAPI Google Flights is the main live flight source when `SERPAPI_API_KEY` exists. FlixBus via RapidAPI is the bus source when `RAPIDAPI_KEY` exists. Travelpayouts widens discovery only when marker/deeplink support exists, or in explicit indicative mode.

Missing provider keys skip providers instead of crashing.

The main table displays only actionable offers: numeric EUR price, operator/company, dates, route and usable booking link. Non-actionable rows remain diagnostics/observations and are not shown as primary results.

## Email

Brevo transactional email API is optional. `EMAIL_ENABLED=false` hides email actions. If enabled, `BREVO_API_KEY` and `EMAIL_FROM` are required.

## Confidence

High: payload has price, destination, core dates. Medium/low: cached, indicative, or incomplete fields. Unknown layovers/connections lower certainty but do not reject alone.

## Limits

Prices can change or disappear. Booking links must be verified before purchase. Visa status is not guaranteed; unknown is safer than blocking.
