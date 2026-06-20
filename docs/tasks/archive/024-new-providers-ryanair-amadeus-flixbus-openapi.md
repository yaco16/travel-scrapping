# 024 - Nouveaux providers : Ryanair, Amadeus, FlixBus Open API

## Statut

Archivee.

## Contexte

`serpapi_google_flights_deals` retourne HTTP 200 `Success` sans cle `deals` pour NCE ete 2026 (smoke confirme 023). Kiwi Tequila ferme aux nouvelles inscriptions. Besoin de providers alternatifs operationnels.

## Nouveaux fichiers

- `travel_scrapping/search/providers/ryanair.py` - Provider vols Ryanair sans cle API. Appel `GET services-api.ryanair.com/farfnd/v4/roundTripFares`. Params: `departureAirportIataCode=NCE`, plage dates, `maxPrice=150`, `currency=EUR`. Parser strict : `fares[]`, iata dest, prix, dates aller/retour, URL booking generee. Confidence `high`.
- `travel_scrapping/search/providers/amadeus.py` - Provider vols Amadeus (inscription gratuite developers.amadeus.com). OAuth2 client_credentials, endpoint `/v1/shopping/flight-destinations`. Confidence `medium`.
- `travel_scrapping/bus/flixbus_openapi.py` - Provider bus FlixBus Open API sans cle (`global.api.flixbus.com`). Recherche city ID par nom, puis trips par city ID. Remplace FlixBus RapidAPI en premier dans la liste bus. Confidence `high` si booking URL present.

## Changements

- `config.py` : ajout `ryanair_enabled=True`, `amadeus_client_id=""`, `amadeus_client_secret=""`, `flixbus_openapi_enabled=True`. Secret fields : `amadeus_client_id`, `amadeus_client_secret`. Warning si credentials Amadeus absents.
- `.env.example` : ajout variables correspondantes.
- `engine.py` : `build_providers()` inclut `RyanairProvider` + `AmadeusProvider` apres SerpApi. Mode bus : `FlixBusOpenApiProvider` en premier, `FlixBusRapidApiProvider` en fallback.
- `provider_role` : `ryanair=primary`, `amadeus=primary`, `flixbus_openapi=optional`.

## Validations

- `pytest tests/providers/test_ryanair.py` : 7 passed.
- `pytest tests/` : 141 passed, 1 warning.
- `ruff check` : No issues found.
- `pyright` (nouveaux fichiers) : 0 errors, 0 warnings, 0 informations.
- `git diff --check` : OK.

## Notes live

- Ryanair : endpoint public, pas d'auth, stable pour les routes depuis NCE (BCN, MAD, DUB, etc.). URL booking directe.
- Amadeus : sandbox gratuit 2000 req/jour. Inscription : `developers.amadeus.com` > Create App > copier client_id + client_secret dans `.env`.
- FlixBus Open API : endpoint non documente officiellement mais stable. Resout les city IDs par nom (Nice -> ID). Si city ID introuvable, retourne 0 offres sans erreur critique.
- FlixBus RapidAPI reste en fallback (403/429 frequents).
