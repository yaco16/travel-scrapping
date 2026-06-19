# Roadmap

## Etat courant

Travel Scrapping MVP construit localement :

- FastAPI + HTMX dashboard sans auth, host par défaut `127.0.0.1`.
- SQLite avec runs, deals, observations prix, statuts providers.
- Date grid NCE round-trip 3-5 nuits jusqu'au 2026-08-31.
- Filtrage budget strict `< 100 EUR`, layover, air time, overnight airport.
- Providers SerpAPI, Travelpayouts, Playwright safe skeleton, tous désactivables sans crash.
- Email Brevo désactivé si `BREVO_API_KEY` ou `EMAIL_FROM` absent.
- CLI, README, `.env.example`, tests et coverage.

## Limite

Aucun sweep live large lancé. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Configurer `.env`, lancer un smoke SerpAPI minimal sur une destination/date, puis ajuster parsing payload réel.
