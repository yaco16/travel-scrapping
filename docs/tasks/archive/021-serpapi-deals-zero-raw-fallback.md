# 021 - SerpApi Deals zero raw fallback

## Statut

Archivee.

## Commits

- Depart: `f65b674a2d44e30b4765da7b336e2cdec7869d1c`
- Final: reporte dans la reponse finale apres push.

## Objectif

Rendre `serpapi_google_flights_deals` robuste quand Google Flight Deals renvoie HTTP 200 sans offres brutes, sans inventer de resultats ni masquer erreur SerpApi.

## Comparaison runs

Runs `11` et `18` ont la meme config et les memes params publics:

- `engine=google_flights_deals`
- `departure_id=NCE`
- `outbound_date=2026-07-01,2026-08-31`
- `trip_length=1,7`
- `max_price=150`
- `stops=2`
- `currency=EUR`
- `gl=fr`
- `hl=fr`
- `adults=1`

Run `11`: HTTP 200, `search_metadata.status=Success`, top-level keys `search_metadata`, `search_parameters`, `departure_informations`, `deals`, `raw_count=30`, `normalized_count=30`, `accepted_count=28`, `rejected_count=2`.

Run `18`: HTTP 200, `search_metadata.status=Success`, top-level keys `search_metadata`, `search_parameters`, `departure_informations`, aucune liste `deals`, `destinations`, `flight_deals`, `best_flights`, `other_flights`, `flights`, `raw_count=0`.

Cause constatee: changement de payload SerpApi/Google pour parametres identiques. L'ancien payload contenait `deals`; le nouveau retourne `Success` sans liste exploitable et sans `error`.

## Resultats

- Diagnostics provider enrichis: `search_metadata.status`, top-level keys, `error` scrubbed, `serpapi_pagination`, params publics sans `api_key`.
- HTTP 200 avec champ `error` marque le provider `ok=false`.
- HTTP 200 sans erreur mais 0 item stocke le diagnostic: `SerpApi appelé, HTTP 200, payload sans deal exploitable.`
- Fallback Deals limite ajoute:
  - `primary_trip_length_1_7`;
  - `fallback_travel_duration_1_week`;
  - `fallback_any_duration`;
  - `fallback_trip_length_3_5`.
- Les probes stoppent des qu'un raw_count positif arrive.
- `request_params_json` contient params publics, `winning_strategy`, `fallback_used`, `fallback_attempts`, `payload_diagnostic`, `diagnostic`.
- `/results` affiche strategie, fallback, attempts compactes, status payload et erreurs sans secret.

## Smoke reel

Run final: `22`.

Params: origine `NCE`, dates `2026-07-01` a `2026-08-31`, budget `150`, nuits `1-7`, max stops app `1` / SerpApi `stops=2`, mode `flight`.

Resultat: 0 partout. SerpApi retourne HTTP 200 `Success` sans liste exploitable pour les 4 attempts.

Provider:

- enabled: `true`
- key_present: `true`
- attempted: `true`
- ok: `true`
- http_status: `200`
- raw_count: `0`
- normalized_count: `0`
- accepted_count: `0`
- rejected_count: `0`
- winning_strategy: `null`
- fallback_used: `true`

Attempts:

- `primary_trip_length_1_7`: HTTP 200, raw 0, normalized 0.
- `fallback_travel_duration_1_week`: HTTP 200, raw 0, normalized 0.
- `fallback_any_duration`: HTTP 200, raw 0, normalized 0.
- `fallback_trip_length_3_5`: HTTP 200, raw 0, normalized 0.

Offres affichees: `0`.

## Validations

- `pytest tests/test_web.py tests/test_templates.py tests/test_formatters.py`: 37 passed, 1 warning.
- `ruff check .`: No issues found.
- `pyright`: 0 errors, 0 warnings, 0 informations.
- `pytest`: 135 passed, 1 warning.
- `pytest --cov --cov-report=term-missing`: 135 passed, 78 warnings, coverage total 89%.
- `git diff --check`: OK.

## Decision

Ne pas inventer d'offres et ne pas basculer vers `google_flights` classique comme source principale. Garder les attempts Deals publics pour diagnostiquer les prochains runs. Investigation future possible cote SerpApi/Google cache si 0 persiste.
