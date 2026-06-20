# Roadmap

## Etat courant

Travel Scrapping MVP construit localement :

- Étape 01 - Correction Jinja `/history` archivee dans `docs/tasks/archive/014-history-date-time-jinja.md`.
- Étape 02 - Cause couverte: `history.html` utilise `run.started_at|date_time`; regression possible si l'environnement Jinja ne declare pas `date_time`.
- Étape 03 - Tests de non-regression ajoutes: compilation de tous les templates via loader Jinja reel, filtres attendus `price_display`/`date_time`, rendu reel `/history` avec Date `JJ/MM/AA HH:mm`.
- Étape 04 - Smoke `/history` reel valide: page complete HTTP 200, colonne Date et date `20/06/26 09:56`.
- Étape 01 - Archives numerotees chronologiquement dans `docs/tasks/archive/001-...` a `013-...`.
- Étape 02 - Historique web enrichi avec Date de lancement du run via `SearchRun.started_at`.
- Étape 03 - Diagnostics fournisseurs visibles par run: actif, cle, appel, HTTP/erreur, brut, normalise, accepte, rejete, raison principale.
- Étape 04 - Message "aucune offre" contextualise par compteurs reels.
- Étape 05 - Correction absence de resultats diagnostiquables: SerpApi compte offres non actionnables, Travelpayouts sans marker reste diagnostique, filtre bus sans rejet `origin mismatch`.
- Étape 01 - Inspection correction date de fin et suivi numerote terminee.
- Étape 02 - Strategy mise a jour et tranche archivee dans `docs/tasks/archive/012-end-date-numbered-steps.md`.
- FastAPI + HTMX dashboard sans auth, host par défaut `127.0.0.1`.
- SQLite avec runs, deals, observations prix, statuts providers.
- Modele commun d'offre avion/bus avec resultats principaux limites a `actionable=true`.
- Étape 03 - Date grid NCE round-trip 3-5 nuits jusqu'au `SEARCH_END_DATE=2026-08-31`; rendu Configuration `jusqu'au 31/08/26`.
- Étape 04 - Suivi numerote visible dans les resultats web/API/CLI.
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

Étape 01 - Verifier abonnement/quota FlixBus RapidAPI avant nouveau smoke live bus: dernier smoke HTTP `429 Too many requests`.
Étape 02 - Ajuster budget ou cible SerpApi seulement apres decision utilisateur: dernier smoke `4` offres brutes, `3` rejetees par budget.
