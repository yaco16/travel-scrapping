# Roadmap

## Etat courant

Travel Scrapping MVP construit localement :

- FastAPI + HTMX dashboard sans auth, host par défaut `127.0.0.1`.
- SQLite avec runs, deals, observations prix, statuts providers.
- Date grid NCE round-trip 3-5 nuits jusqu'au `SEARCH_END_DATE=2026-08-30`.
- Filtrage budget strict `< 100 EUR`, layover, air time, overnight airport.
- Providers SerpAPI, Travelpayouts, Playwright safe skeleton, tous désactivables sans crash.
- Resultats UI normalises : ville francaise, dates JJ/MM/AA, prix entier, compagnies/warnings/lien lisibles.
- Resultats limites aux deals valides du dernier run ; sejours hors 3-5 nuits masques meme si la base contient d'anciennes lignes invalides.
- Historique integre un diagnostic base de donnees ; `/sqlite` reste disponible en debug local hors menu principal.
- Email Brevo optionnel et masque par defaut via `EMAIL_ENABLED=false`.
- Historique `price_observations` append-only enrichi, diagnostic CLI et `/sqlite`.
- Enrichissement aeroport optionnel via API Ninjas Airports, cache SQLite `airport_metadata`, fallback villes francaises sans cle API.
- CLI `airports-refresh` pour backfill/refresh des metadonnees aeroport.
- CLI, README, `.env.example`, tests et coverage.

## Limite

Aucun sweep live large lancé. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Configurer `.env`, lancer `airports-refresh --iata VCE` si cle API Ninjas disponible, puis lancer un smoke SerpAPI minimal sur une destination/date et ajuster parsing payload reel.
