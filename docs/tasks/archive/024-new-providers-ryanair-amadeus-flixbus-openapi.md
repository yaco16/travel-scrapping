# 024 - Nouveaux providers : Ryanair, Amadeus, FlixBus Open API

## Statut

Archivee.

## Contexte

`serpapi_google_flights_deals` retourne HTTP 200 `Success` sans cle `deals` pour NCE ete 2026 (smoke confirme 023). Kiwi Tequila ferme aux nouvelles inscriptions. Besoin de providers alternatifs operationnels.

## Nouveaux fichiers

- `travel_scrapping/search/providers/ryanair.py` - Provider vols Ryanair sans cle API. Appel `GET services-api.ryanair.com/farfnd/v4/roundTripFares`. Params: `departureAirportIataCode=NCE`, plage dates, `maxPrice=150`, `currency=EUR`. Parser strict : `fares[]`, iata dest, prix, dates aller/retour, URL booking generee. Confidence `high`.
- `travel_scrapping/search/providers/amadeus.py` - Provider vols Amadeus (inscription gratuite developers.amadeus.com). OAuth2 client_credentials, endpoint `/v1/shopping/flight-destinations`. Confidence `medium`.
- `travel_scrapping/bus/flixbus_openapi.py` - Provider bus FlixBus Open API sans cle (`global.api.flixbus.com`). Branche le diagnostic ville/trajet, mais l'endpoint actuel teste pour la ville n'est pas une recherche texte et exige déjà un `from_city_id` ou `to_city_id`. Remplace FlixBus RapidAPI en premier dans la liste bus. Confidence `high` si booking URL present.

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
- FlixBus Open API : branche, mais non exploitable avec l'endpoint actuel, car `cities/details` n'est pas une recherche texte et exige déjà un `from_city_id` ou `to_city_id`. Constat live: HTTP 400, message `At least one of parameters from_city_id and to_city_id should be present`. Le probleme n'est pas l'absence generique d'un lookup `city_id`, mais le fait que l'endpoint teste ne permet pas de transformer un nom de ville comme Nice ou Paris en city_id. Aucun city_id invente, aucune offre fictive creee.
- FlixBus RapidAPI reste en fallback (403/429 frequents).
