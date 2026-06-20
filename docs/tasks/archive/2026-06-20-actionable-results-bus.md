# Rapport final - resultats actionnables et bus

Statut: archive.

Start commit: `13c62284bcddc7f7d4d99cad2b6aa8619318f61b`
Final commit: renseigne dans le rapport final utilisateur apres push.

## Resultats

- Amadeus absent et documente comme non utilise.
- OurAirports importe en SQLite depuis `data/sources/ourairports/airports.csv`.
- Resolution aeroport: cache, OurAirports, API Ninjas, fallback.
- SerpApi Google Flights: smoke multi-etapes, debug JSON, tokens, booking options.
- Travelpayouts sans marker exclu des resultats principaux sauf mode indicatif explicite.
- Modele commun `Offer` ajoute pour avion/bus, avec actionnabilite stricte.
- Module bus FlixBus RapidAPI ajoute, host/base URL lus depuis env.
- Recherche combinee `--modes flight,bus`.
- Front: filtres Tous/Avion/Bus, table principale actionnable, diagnostics si vide.
- Formatters FR communs.

## Validations

- Tests cibles: OK.
- Suite: `68 passed`.
- Coverage: `82%`.
- Ruff: OK.
- Pyright: OK.
- `git diff --check`: OK.
- CLI:
  - `airports-import-ourairports --force-refresh`: 9055 imports.
  - `airports-refresh --iata VCE`: OK, cache prioritaire.
  - `airports-diagnostics`: OK.
  - `serpapi-smoke`: HTTP 200, status Success, 2 departure tokens, 2 booking tokens, 29 booking options.
  - `flixbus-smoke`: `RAPIDAPI_KEY missing`.
  - `sqlite-diagnostics`: OK, 18 observations invalides historiques detectees.

## Decision

La table principale n'affiche que des offres actionnables. Les sources incompletes restent diagnostiques/indicatives.
