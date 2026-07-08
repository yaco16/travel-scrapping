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
- Provider `flixbus_openapi` utilise cache `id` UUID + `legacy_id` séparé depuis autocomplete mobile FlixBus; `cities/details` n'est plus utilisé comme recherche texte. Search trajet appelé par défaut avec UUID `id` non ambigus. `legacy_id` reste diagnostic ou smoke explicite. FlixBus RapidAPI reste en fallback.
- GTFS officiel FlixBus/FlixTrain ajoute en cache local explicite `data/gtfs/flixbus/gtfs_generic_eu.zip`; source réseau/arrêts/lignes/horaires, pas source prix/réservation.
- Provider `comparabus` ajoute pour bus: stops/routes/prices publics ComparaBUS + redirect explicite, confiance `medium`, aucune offre si stop ambigu ou lien absent.
- Provider `distribusion` socle bus + train Europe, desactive par defaut.
- `engine.py` `build_providers()` = SerpApi Deals + Ryanair + Amadeus + Travelpayouts + Playwright. Mode bus = Comparabus + FlixBus Open API + FlixBus RapidAPI.
- `config.py` : `ryanair_enabled`, `amadeus_client_id`, `amadeus_client_secret`, `flixbus_openapi_enabled`, `comparabus_enabled`, `comparabus_base_url`.
- Diagnostics `/results` affichent tous les providers avec compteurs, HTTP status, params publics.
- Diagnostics fournisseurs exposent `distribusion` meme desactive, sans secret.
- SQLite reste compatible: `transport_mode` string, anciennes lignes conservees.

## Limite

Smoke reel Deals strict NCE ete 2026: HTTP 200 `Success`, 0 cle `deals`, raw 0. Aucun faux resultat cree. FlixBus RapidAPI retourne `403/429`. FlixBus Open API live 2026-06-20: `cities/details?q=Nice` retourne HTTP 400 avec le message `At least one of parameters from_city_id and to_city_id should be present`; cet endpoint ne transforme pas Nice/Paris en city_id. GTFS OK pour réseau/arrêts/horaires. Autocomplete OK: Nice `id=40e13a46-8646-11e6-9066-549f350fcb0c`, `legacy_id=6608`; Paris `id=40de8964-8646-11e6-9066-549f350fcb0c`, `legacy_id=2015`. Search UUID + `departure_date=30.07.2026` + `products={"adult":1}` retourne HTTP 200, 14 trajets bruts, 0 offre car aucun lien réservation explicite observé. Search legacy `6608/2015` retourne HTTP 400 `Signature "6608" for class "FlixTech\\SearchService\\Domain\\General\\CityId" is invalid`. Aucun city_id invente, aucune offre fictive creee. Ryanair + Amadeus : non encore testes live en 024 (tests unitaires offline uniquement).

## Prochaine tranche

- Etape 01 - Smoke live Ryanair depuis NCE : fait, resultats reels obtenus (cf. TODO.md).
- Etape 02 - Abandonnee : Amadeus non configure sur decision utilisateur (API bientot retiree). Travelpayouts configure a la place (token + marker, deep link Aviasales construit cote code) : offres reelles actionables en live (cf. TODO.md).
- Etape 03 - FlixBus Open API : trouver un lien réservation contractuel dans payload/API ou basculer sur fournisseur bus contractuel. Garder 0 offre tant que lien réservation explicite absent.
- Etape 04 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
