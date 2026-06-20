# 022 - Google Travel Explore provider smoke

## Statut

Archivee, diagnostic seulement.

## Commits

- Depart: `ok520c85a38a9e47cadffd523ef196c381855d6829`
- Final: reporte apres push.

## Objectif

Tester `engine=google_travel_explore` comme provider avion principal potentiel, car l'ecran Google visible affiche des resultats tandis que `google_flights_deals` retourne HTTP 200 sans liste `deals`.

## Smoke reel exploratoire

Endpoint: `google_travel_explore`.

Params communs publics:

- `engine=google_travel_explore`
- `departure_id=NCE`
- `type=1`
- `currency=EUR`
- `gl=fr`
- `hl=fr`
- `adults=1`
- `max_price=150`
- `stops=2`
- `travel_mode=1`

Variantes:

- A: `outbound_date=2026-07-16`, `return_date=2026-07-23`
- B: `outbound_date=2026-07-21`, `return_date=2026-07-28`
- C: `outbound_date=2026-08-28`, `return_date=2026-08-31`
- D: `outbound_date=2026-07-01`, `return_date=2026-07-08`

Resultat pour les 4 variantes:

- HTTP: `200`
- `search_metadata.status`: `Success`
- top-level keys: `search_metadata`, `search_parameters`, `search_information`, `error`
- listes exploitables: aucune `destinations`, aucune `flights`, aucune `deals`
- brut: `0`
- exemples destination/prix: aucun
- SVQ/STN/FCO: absents
- erreur SerpApi: `Empty results for departure_id: "NCE".`

Debug JSON scrubbed:

- `data/debug/serpapi-google-travel-explore-smoke-a-20260620T163528Z.json`
- `data/debug/serpapi-google-travel-explore-smoke-b-20260620T163529Z.json`
- `data/debug/serpapi-google-travel-explore-smoke-c-20260620T163529Z.json`
- `data/debug/serpapi-google-travel-explore-smoke-d-20260620T163530Z.json`

## Implementation

- Ajout outil smoke propre: `tools/smoke_google_travel_explore.py`.
- Pas de provider `SerpApiGoogleTravelExploreProvider` integre, car le gate exploratoire retourne 0 partout.
- Pas de modification moteur/UI hors documentation.
- Aucun changement `.env`, aucun secret expose, aucun resultat invente.
- Bus/train inchanges, Distribusion reste scaffold desactive.

## Validations

- `pytest tests/test_web.py tests/test_templates.py tests/test_formatters.py`: 37 passed, 1 warning.
- `ruff check .`: No issues found.
- `pyright`: 0 errors, 0 warnings, 0 informations.
- `pytest`: 135 passed, 1 warning.
- `pytest --cov --cov-report=term-missing`: 135 passed, 78 warnings, coverage total 89%.
- `git diff --check`: OK.

## Decision

Ne pas integrer `google_travel_explore` comme provider principal dans cet etat. Prochaine action utile: clarifier avec SerpApi le support de `departure_id=NCE` pour `google_travel_explore` ou tester une forme officielle supplementaire documentee par SerpApi, sans inventer d'offres.
