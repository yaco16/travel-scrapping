# Travel Scrapping

FastAPI + HTMX dashboard for very cheap round-trip flight deals from Nice (NCE).

Defaults: one adult, personal item only, no checked/cabin bag, 3-5 nights, under 100 EUR total, from today to 2026-08-31, max 5h air time per direction, max 3h layover, no overnight airport stay.

## Setup

```bash
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with available keys. Keep `.env` untracked.

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
.venv/bin/python -m travel_scrapping.cli search --send-email
```

## Tests

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov --cov-report=term-missing
```

## Providers

SerpAPI Google Flights is the main live source when `SERPAPI_API_KEY` exists. Travelpayouts widens discovery and is marked medium/low confidence, especially without marker/deeplink support. Playwright is a safe disabled skeleton: no CAPTCHA bypass, no login bypass, no proxy rotation, no rate-limit evasion.

Missing provider keys skip providers instead of crashing.

## Email

Brevo transactional email API is used. `BREVO_API_KEY` and `EMAIL_FROM` are required. Without sender, email is disabled and dashboard warns.

## Confidence

High: payload has price, destination, core dates. Medium/low: cached, indicative, or incomplete fields. Unknown layovers/connections lower certainty but do not reject alone.

## Limits

Prices can change or disappear. Booking links must be verified before purchase. Visa status is not guaranteed; unknown is safer than blocking.
