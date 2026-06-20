# Roadmap

## Etat courant

Travel Scrapping MVP local:

- Tranche `020-flight-regression-after-ground-scaffold` archivee dans `docs/tasks/archive/020-flight-regression-after-ground-scaffold.md`.
- Modes transport supportes: `flight`, `bus`, `train`; affichages `Avion`, `Bus`, `Train`; `/results` propose onglets `Tous`, `Avion`, `Bus`, `Train`; `all` inclut les trois modes.
- Regression avion post-scaffold corrigee cote selection modes: fallback `flight`, relance home conserve les modes du run, `run_search` construit toujours le provider avion quand `flight` est demande.
- Diagnostics `/results` differencient absence de provider actif, SerpApi desactive, HTTP SerpApi non 200 et SerpApi appele avec 0 offre brute; `serpapi_google_flights_deals` reste visible meme a 0 resultat.
- Provider `distribusion` ajoute comme socle bus + train Europe, desactive par defaut, sans appel reseau et sans offres fictives tant que credentials et API docs contractuelles manquent.
- Diagnostics fournisseurs exposent `distribusion` desactive avec `attempted=false`, `key_present` selon config, warning `DISTRIBUSION credentials missing`, sans secret brut.
- FlixBus RapidAPI reste provider bus secondaire existant.
- SQLite reste compatible: `transport_mode` est une string, anciennes lignes `flight` / `bus` conservees.
- Formats UI/API conserves: dates `JJ/MM/AA`, prix francais, provider, operator, booking URL si disponible.
- Documentation providers: Distribusion prioritaire futur bus + train Europe; Transitland/GTFS pour decouverte operateurs/routes/arrets/horaires, pas prix/reservation; OSDM utile via agregateur au depart.

## Limite

Smoke reel NCE `2026-07-01,2026-08-31`, budget 150, nuits 1-7, mode flight: `serpapi_google_flights_deals` appele, HTTP 200, params attendus, mais SerpApi retourne 0 offre brute au run `18`. Aucun sweep live large lancé. FlixBus live teste avec `RAPIDAPI_KEY`, mais RapidAPI retourne `403/429` (`You are not subscribed to this API` / `Too many requests`) et aucune offre actionnable n'est récupérée. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Étape 01 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
Étape 02 - Apres acces valide, implementer l'appel reel `distribusion` bus + train Europe sans faux resultats.
Étape 03 - Si besoin produit, investiguer pourquoi SerpApi Deals retourne 0 offre brute sur NCE ete 2026 nuits 1-7 alors que des runs 3-5 ont retourne des deals.
