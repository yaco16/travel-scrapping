# Roadmap

## Etat courant

Travel Scrapping MVP local:

- Tranche `023-google-flight-deals-strict-provider` archivee dans `docs/tasks/archive/023-google-flight-deals-strict-provider.md`.
- Modes transport supportes: `flight`, `bus`, `train`; affichages `Avion`, `Bus`, `Train`; `/results` propose onglets `Tous`, `Avion`, `Bus`, `Train`; `all` inclut les trois modes.
- Provider avion principal `serpapi_google_flights_deals` strict: un appel `engine=google_flights_deals`, `departure_id=NCE`, `type=1`, `outbound_date=2026-07-01,2026-08-31`, `trip_length=1,7`, `max_price=150`, `stops=2`, `currency=EUR`, `gl=fr`, `hl=fr`, `adults=1`, aucun `return_date`.
- Parser Deals limite a la cle `deals`; si payload vide ou sans `deals`, aucune offre n'est inventee et aucune observation prix n'est persistee.
- `google_travel_explore` non integre comme provider.
- Diagnostics `/results` affichent endpoint Deals, HTTP, compteurs, status metadata, top-level keys et params publics sans `api_key`; `serpapi_google_flights_deals` reste visible meme a 0 resultat.
- Provider `distribusion` ajoute comme socle bus + train Europe, desactive par defaut, sans appel reseau et sans offres fictives tant que credentials et API docs contractuelles manquent.
- Diagnostics fournisseurs exposent `distribusion` desactive avec `attempted=false`, `key_present` selon config, warning `DISTRIBUSION credentials missing`, sans secret brut.
- FlixBus RapidAPI reste provider bus secondaire existant.
- SQLite reste compatible: `transport_mode` est une string, anciennes lignes `flight` / `bus` conservees.
- Formats UI/API conserves: dates `JJ/MM/AA`, prix francais, provider, operator, booking URL si disponible.
- Documentation providers: Distribusion prioritaire futur bus + train Europe; Transitland/GTFS pour decouverte operateurs/routes/arrets/horaires, pas prix/reservation; OSDM utile via agregateur au depart.

## Limite

Smoke reel Deals strict NCE ete 2026: HTTP 200 `Success`, top-level keys `search_metadata`, `search_parameters`, `departure_informations`, 0 cle `deals`, raw 0, normalized 0, accepted 0, rejected 0, SVQ/STN/FCO absents, aucune observation prix persistee. Aucun faux resultat cree. FlixBus live teste avec `RAPIDAPI_KEY`, mais RapidAPI retourne `403/429` (`You are not subscribed to this API` / `Too many requests`) et aucune offre actionnable n'est récupérée. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Étape 01 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
Étape 02 - Apres acces valide, implementer l'appel reel `distribusion` bus + train Europe sans faux resultats.
Étape 03 - Clarifier avec SerpApi pourquoi `google_flights_deals` retourne HTTP 200 `Success` sans cle `deals` sur NCE ete 2026 alors que Google UI affiche des offres.
