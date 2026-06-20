# 023 - Google Flight Deals strict provider

## Statut

Archivee.

## Commits

- Depart: `9ff22b65b56bf7a4554310c78bda15d3927a801c`
- Final: reporte apres push.

## Objectif

Corriger `serpapi_google_flights_deals` uniquement. Ne pas integrer `google_travel_explore`.

## Changements

- Provider Deals reduit a un seul appel strict `google_flights_deals`.
- Params publics:
  - `engine=google_flights_deals`
  - `departure_id=NCE`
  - `type=1`
  - `outbound_date=2026-07-01,2026-08-31`
  - `trip_length=1,7`
  - `max_price=150`
  - `stops=2`
  - `currency=EUR`
  - `gl=fr`
  - `hl=fr`
  - `adults=1`
- Aucun `return_date` envoye avec `trip_length`.
- Parser limite a la cle `deals`.
- Suppression du smoke outil `google_travel_explore`; Explore reste non integre.
- Ajout smoke reel dedie `tools/smoke_google_flight_deals.py`.
- Diagnostics `/results` sans strategie fallback obsolète.
- Aucune observation prix n'est persistee si aucune offre normalisee valide.
- Bus/train inchanges.

## Smoke reel Deals

Commande: `rtk run '.venv/bin/python tools/smoke_google_flight_deals.py'`.

Resultat:

- endpoint: `google_flights_deals`
- HTTP: `200`
- `search_metadata.status`: `Success`
- top-level keys: `search_metadata`, `search_parameters`, `departure_informations`
- raw_count: `0`
- normalized_count: `0`
- accepted_count: `0`
- rejected_count: `0`
- SVQ/STN/FCO: absents
- debug JSON: `data/debug/serpapi-google-flight-deals-20260620T173938Z.json`

## Validations

- `pytest tests/providers/test_serpapi_google_flights.py tests/test_engine.py tests/test_web.py tests/test_templates.py tests/test_formatters.py`: 64 passed, 1 warning.
- `ruff check .`: No issues found.
- `pyright`: 0 errors, 0 warnings, 0 informations.
- `pytest`: 134 passed, 1 warning.
- `pytest --cov --cov-report=term-missing`: 134 passed, 80 warnings, coverage total 89%.
- `git diff --check`: OK.

## Decision

Ne pas inventer d'offres et ne pas integrer `google_travel_explore`. Garder Deals strict comme provider avion principal; escalader cote SerpApi si HTTP 200 `Success` continue sans cle `deals`.
