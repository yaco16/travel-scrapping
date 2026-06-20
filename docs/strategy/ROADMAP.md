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
- Smoke FlixBus live instrumente: host RapidAPI derive par defaut, statuts HTTP/endpoint/erreurs visibles en CLI et diagnostics SQLite, erreurs scrubbees.
- Endpoint `GET /deals` expose les meilleures offres SQLite normalisees du dernier run.
- Front `/results` affiche offres actionnables avec destination, dates JJ/MM/AA, prix francais, nuits, provider et statut provider.
- Front `/search` cree un `run_id`, lance la recherche en tache backend non bloquante et redirige vers `/results?run_id=...`.
- `/results` filtre par `run_id` si fourni, sinon affiche le dernier run.
- `/results` affiche statut `pending`, `running`, `completed` ou `failed` avec auto-refresh leger tant que le run n'est pas terminal.
- Erreurs FlixBus RapidAPI `403/429` affichees proprement sans secret et sans echec page.
- Insertion SQLite des observations prix protegee: `run_id` obligatoire, champs normalises indispensables non nuls, diagnostics/variations ignorent les lignes historiques invalides.
- CLI `sqlite-clean-invalid --dry-run|--execute` disponible pour nettoyer les anciennes observations corrompues de developpement local sans supprimer les campagnes.
- CLI, README, `.env.example`, tests et coverage.
- Couverture tests renforcée: 94 tests, coverage total 91%, aucun fichier Python sous 80%.

## Limite

Aucun sweep live large lancé. FlixBus live teste avec `RAPIDAPI_KEY`, mais RapidAPI retourne `403/429` (`You are not subscribed to this API` / `Too many requests`) et aucune offre actionnable n'est récupérée. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Utiliser le parcours front non bloquant `/search` -> `/results?run_id=...` sur donnees reelles, puis verifier abonnement/quota RapidAPI Flixbus2 avant tout nouveau smoke live bus.
