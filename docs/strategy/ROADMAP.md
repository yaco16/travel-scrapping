# Roadmap

## Etat courant

Travel Scrapping MVP construit localement :

- FastAPI + HTMX dashboard sans auth, host par défaut `127.0.0.1`.
- SQLite avec runs, deals, observations prix, statuts providers.
- Modele commun d'offre avion/bus avec resultats principaux limites a `actionable=true`.
- Date grid NCE round-trip 3-5 nuits jusqu'au `SEARCH_END_DATE=2026-08-30`.
- Filtrage budget strict `< 100 EUR`, layover, air time, overnight airport.
- Providers SerpAPI, FlixBus RapidAPI, Travelpayouts indicatif, Playwright safe skeleton, tous désactivables sans crash.
- Resultats UI normalises : modes avion/bus, ville francaise, dates JJ/MM/AA, prix francais, operateur, duree, lien actionnable.
- Resultats limites aux deals valides du dernier run ; sejours hors 3-5 nuits masques meme si la base contient d'anciennes lignes invalides.
- Historique integre un diagnostic base de donnees ; `/sqlite` reste disponible en debug local hors menu principal.
- Email Brevo optionnel et masque par defaut via `EMAIL_ENABLED=false`.
- Historique `price_observations` append-only enrichi, diagnostic CLI et `/sqlite`.
- Enrichissement aeroport via cache SQLite, OurAirports local, API Ninjas fallback, fallback villes francaises sans cle API.
- CLI `airports-import-ourairports`, `airports-refresh`, `airports-diagnostics`.
- CLI `serpapi-smoke`, `flixbus-smoke`, `bus-stations-search`.
- Insertion SQLite des observations prix protegee: `run_id` obligatoire, champs normalises indispensables non nuls, diagnostics/variations ignorent les lignes historiques invalides.
- CLI `sqlite-clean-invalid --dry-run|--execute` disponible pour nettoyer les anciennes observations corrompues de developpement local sans supprimer les campagnes.
- CLI, README, `.env.example`, tests et coverage.

## Limite

Aucun sweep live large lancé. FlixBus live non teste sans `RAPIDAPI_KEY`. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Configurer `RAPIDAPI_KEY`/host FlixBus2, lancer `bus-stations-search` puis `flixbus-smoke`, et ajuster les endpoints si la documentation RapidAPI differe.
