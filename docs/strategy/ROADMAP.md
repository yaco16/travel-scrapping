# Roadmap

## Etat courant

Travel Scrapping MVP local:

- Tranche `019-ground-transport-scaffold` archivee dans `docs/tasks/archive/019-ground-transport-scaffold.md`.
- Modes transport supportes: `flight`, `bus`, `train`; affichages `Avion`, `Bus`, `Train`; `/results` propose onglets `Tous`, `Avion`, `Bus`, `Train`; `all` inclut les trois modes.
- Provider `distribusion` ajoute comme socle bus + train Europe, desactive par defaut, sans appel reseau et sans offres fictives tant que credentials et API docs contractuelles manquent.
- Diagnostics fournisseurs exposent `distribusion` desactive avec `attempted=false`, `key_present` selon config, warning `DISTRIBUSION credentials missing`, sans secret brut.
- FlixBus RapidAPI reste provider bus secondaire existant.
- SQLite reste compatible: `transport_mode` est une string, anciennes lignes `flight` / `bus` conservees.
- Formats UI/API conserves: dates `JJ/MM/AA`, prix francais, provider, operator, booking URL si disponible.
- Documentation providers: Distribusion prioritaire futur bus + train Europe; Transitland/GTFS pour decouverte operateurs/routes/arrets/horaires, pas prix/reservation; OSDM utile via agregateur au depart.

## Limite

Aucun sweep live large lancé. FlixBus live teste avec `RAPIDAPI_KEY`, mais RapidAPI retourne `403/429` (`You are not subscribed to this API` / `Too many requests`) et aucune offre actionnable n'est récupérée. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Étape 01 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
Étape 02 - Apres acces valide, implementer l'appel reel `distribusion` bus + train Europe sans faux resultats.
Étape 03 - Si besoin produit, investiguer NCE-SVQ en discovery `anywhere`: probe cible trouve l'offre, le global SerpApi Deals ne la renvoie pas.
