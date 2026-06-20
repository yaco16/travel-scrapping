# Roadmap

## Etat courant

Travel Scrapping MVP local:

- Tranche `022-google-travel-explore-provider` archivee dans `docs/tasks/archive/022-google-travel-explore-provider.md`.
- Modes transport supportes: `flight`, `bus`, `train`; affichages `Avion`, `Bus`, `Train`; `/results` propose onglets `Tous`, `Avion`, `Bus`, `Train`; `all` inclut les trois modes.
- Provider avion `serpapi_google_flights_deals` robuste aux payloads HTTP 200 sans deal: diagnostics payload publics, champ `error` SerpApi en `ok=false`, diagnostic explicite si 0 brut sans erreur.
- Fallback Deals limite documente: `primary_trip_length_1_7`, `fallback_travel_duration_1_week`, `fallback_any_duration`, `fallback_trip_length_3_5`; stop au premier `raw_count > 0`; normalisation/filtrage inchanges.
- Smoke reel `google_travel_explore` realise sur 4 paires datees NCE ete 2026: HTTP 200 `Success`, mais top-level keys `search_metadata`, `search_parameters`, `search_information`, `error`, 0 `destinations`, 0 `flights`, 0 brut, erreur `Empty results for departure_id: "NCE".`; provider non integre pour eviter toute offre inventee.
- Diagnostics `/results` affichent strategie gagnante, fallback utilisee, attempts compactes, status metadata, top-level keys et params publics sans `api_key`; `serpapi_google_flights_deals` reste visible meme a 0 resultat.
- Provider `distribusion` ajoute comme socle bus + train Europe, desactive par defaut, sans appel reseau et sans offres fictives tant que credentials et API docs contractuelles manquent.
- Diagnostics fournisseurs exposent `distribusion` desactive avec `attempted=false`, `key_present` selon config, warning `DISTRIBUSION credentials missing`, sans secret brut.
- FlixBus RapidAPI reste provider bus secondaire existant.
- SQLite reste compatible: `transport_mode` est une string, anciennes lignes `flight` / `bus` conservees.
- Formats UI/API conserves: dates `JJ/MM/AA`, prix francais, provider, operator, booking URL si disponible.
- Documentation providers: Distribusion prioritaire futur bus + train Europe; Transitland/GTFS pour decouverte operateurs/routes/arrets/horaires, pas prix/reservation; OSDM utile via agregateur au depart.

## Limite

Smoke reel Deals NCE `2026-07-01,2026-08-31`, budget 150, nuits 1-7, mode flight: run `22`, 4 probes Deals appelees, HTTP 200 `Success`, top-level keys `search_metadata`, `search_parameters`, `departure_informations`, 0 offre brute partout, 0 offre affichee. Smoke Explore NCE dates exactes SVQ/STN/FCO/D: HTTP 200 `Success` mais `error="Empty results for departure_id: "NCE"."`, 0 liste exploitable. Aucun faux resultat cree. Aucun sweep live large lancé. FlixBus live teste avec `RAPIDAPI_KEY`, mais RapidAPI retourne `403/429` (`You are not subscribed to this API` / `Too many requests`) et aucune offre actionnable n'est récupérée. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Étape 01 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
Étape 02 - Apres acces valide, implementer l'appel reel `distribusion` bus + train Europe sans faux resultats.
Étape 03 - Clarifier avec SerpApi pourquoi `google_flights_deals` et `google_travel_explore` retournent HTTP 200 `Success` sans liste exploitable sur NCE ete 2026 alors que Google UI affiche des offres.
