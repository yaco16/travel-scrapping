# Rapport final - FlixBus live smoke

## Statut

Archive: validation technique OK, recuperation live bloquee par RapidAPI.

## Commits

- Depart: `933e0d8cf8dbc16c36a8578a1c5c1ca6e4d92a7e`
- Final: a renseigner apres commit.

## Resultats

- `RAPIDAPI_KEY` presente.
- `FLIXBUS_RAPIDAPI_HOST` derive par defaut depuis `FLIXBUS_RAPIDAPI_BASE_URL`.
- `bus-stations-search --query "Nice"` retourne `statut_http=429`, `error=Too many requests`.
- `flixbus-smoke Nice -> Venise` retourne `stations=0`, `offres=0`, `statut_http=429`.
- E2E bus limite cree `run_id=5` en SQLite.
- Diagnostics SQLite affichent le statut provider FlixBus: `ok=False`, `error=You are not subscribed to this API.`.
- Aucune offre FlixBus live actionnable n'a pu etre normalisee/stockee, car RapidAPI refuse l'acces.
- Erreurs provider scrubbees avant stockage/affichage pour eviter fuite de secrets.

## Validations

- Tests cibles: `14 passed`.
- Ruff: OK.
- Pyright: OK, `0 errors`.
- Diff check: OK.
- Suite integrale: `69 passed`, coverage `81%`.

## Decision

Garder les corrections diagnostics/host. Prochaine action: verifier abonnement/quota RapidAPI Flixbus2 avant nouveau smoke live.
