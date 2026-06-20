# Roadmap

## Etat courant

Travel Scrapping MVP local:

- Tranche `023-google-flight-deals-strict-provider` archivee dans `docs/tasks/archive/023-google-flight-deals-strict-provider.md`.
- Tranche `024-new-providers-ryanair-amadeus-flixbus-openapi` archivee dans `docs/tasks/archive/024-new-providers-ryanair-amadeus-flixbus-openapi.md`.
- Modes transport supportes: `flight`, `bus`, `train`; affichages `Avion`, `Bus`, `Train`; `/results` propose onglets `Tous`, `Avion`, `Bus`, `Train`; `all` inclut les trois modes.
- Provider avion principal `serpapi_google_flights_deals` strict: un appel `engine=google_flights_deals`, `departure_id=NCE`, `type=1`, `outbound_date=2026-07-01,2026-08-31`, `trip_length=1,7`, `max_price=150`, `stops=2`, `currency=EUR`, `gl=fr`, `hl=fr`, `adults=1`, aucun `return_date`.
- Parser Deals limite a la cle `deals`; si payload vide ou sans `deals`, aucune offre n'est inventee et aucune observation prix n'est persistee.
- `google_travel_explore` non integre comme provider.
- Provider `ryanair` ajoute : `GET services-api.ryanair.com/farfnd/v4/roundTripFares`, sans cle API, confidence `high`.
- Provider `amadeus` ajoute : OAuth2 `test.api.amadeus.com/v1/shopping/flight-destinations`, credentials gratuits requis.
- Provider `flixbus_openapi` ajoute : `global.api.flixbus.com` sans cle, premier provider bus. FlixBus RapidAPI reste en fallback.
- Provider `distribusion` socle bus + train Europe, desactive par defaut.
- `engine.py` `build_providers()` = SerpApi Deals + Ryanair + Amadeus + Travelpayouts + Playwright. Mode bus = FlixBus Open API + FlixBus RapidAPI.
- `config.py` : `ryanair_enabled`, `amadeus_client_id`, `amadeus_client_secret`, `flixbus_openapi_enabled`.
- Diagnostics `/results` affichent tous les providers avec compteurs, HTTP status, params publics.
- SQLite reste compatible: `transport_mode` string, anciennes lignes conservees.

## Limite

Smoke reel Deals strict NCE ete 2026: HTTP 200 `Success`, 0 cle `deals`, raw 0. Aucun faux resultat cree. FlixBus RapidAPI retourne `403/429`. Ryanair + Amadeus + FlixBus Open API : non encore testes live en 024 (tests unitaires offline uniquement).

## Prochaine tranche

- Etape 01 - Smoke live Ryanair depuis NCE : lancer `search --modes flight` et verifier resultats ryanair dans diagnostics.
- Etape 02 - Creer compte Amadeus (`developers.amadeus.com`), renseigner `AMADEUS_CLIENT_ID` + `AMADEUS_CLIENT_SECRET` dans `.env`, smoke live.
- Etape 03 - Smoke live FlixBus Open API : verifier city ID Nice et trajets bus.
- Etape 04 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
