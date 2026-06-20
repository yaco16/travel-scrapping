# Roadmap

## Etat courant

Travel Scrapping MVP construit localement :

- Étape 01 - Tranche `018-results-pipeline-no-spinner` archivee dans `docs/tasks/archive/018-results-pipeline-no-spinner.md`.
- Étape 02 - `/results` affiche le pipeline sans spinner; `pending` reste visible et clignotant, auto-refresh non terminal conserve.
- Étape 03 - Tests UI gardent les garanties HTMX/onglets sans retour haut, pays pres de la ville, meilleur prix vert et `/search` redirige vers `/`.
- Étape 04 - Documentation providers: pas de nouvelle API integree maintenant; `Distribusion` est candidat prioritaire futur bus + train Europe; `Transitland/GTFS` sert a decouvrir operateurs/routes/arrets/horaires sans prix/reservation; `OSDM` est un standard rail utile a privilegier via agregateur au depart; provider futur possible `ground_transport_distribusion` desactive par defaut sans credentials.
- Étape 01 - Tranche `017-ui-results-polish` archivee dans `docs/tasks/archive/017-ui-results-polish.md`.
- Étape 02 - `/search` redirige vers `/` en `303`; le menu principal garde Dashboard, Résultats, Historique; la home conserve le formulaire de recherche.
- Étape 03 - La home masque uniquement le warning `Travelpayouts désactivé : TRAVELPAYOUTS_MARKER manquant`; `/results` conserve le diagnostic Travelpayouts.
- Étape 04 - `/results` affichait spinner pipeline, `pending` clignotant, auto-refresh non terminal, onglets HTMX Tous/Avion/Bus sans retour haut avec fallback ancre.
- Étape 05 - Le meilleur prix est vert, les pays destinations s'affichent près des villes via `destination_country` ou fallback aeroport, codes connus traduits en francais.
- Étape 06 - Documentation providers ajoute `Distribusion` comme candidat futur bus/train Europe; `Transitland/GTFS` et `OSDM` restent documentation seulement.
- Étape 01 - Tranche `016-run-snapshot-results-ui-providers` archivee dans `docs/tasks/archive/016-run-snapshot-results-ui-providers.md`.
- Étape 02 - Cause `44,00 €` corrigee: `/results` reappliquait `.env` courant `100 EUR` / `3-5 nuits` au lieu du snapshot run; STN `44,00 €` etait en DB/agregat mais filtree.
- Étape 03 - `search_runs` stocke `config_json` et `providers_json`; `/results`, homepage et historique affichent les chiffres/config du run, avec fallback legacy depuis diagnostics provider.
- Étape 04 - `/results` affiche toutes les offres acceptees du run, tri prix/date/destination, compteur `offres affichées sur acceptées`, badge `Meilleur prix`; smoke reel run #11 valide `28` acceptees, `2` rejetees, meilleur prix `44,00 €`.
- Étape 05 - Homepage refaite: configuration par defaut separee du dernier run, carte dernier run avec ID/date/statut/config/offres/meilleur prix, boutons `Voir les résultats` et `Relancer avec cette configuration`.
- Étape 06 - CSS homepage/resultats refait avec skill globale `prototype`: hero, metriques, tabs, cards resultats, providers, diagnostics secondaires, responsive mobile.
- Étape 07 - Providers rationalises dans `docs/providers.md`: SerpApi Deals primaire, SerpApi Flights probe detail, Travelpayouts optional desactive sans marker, FlixBus optional masque si `403/429`, Playwright probe diagnostics avances.
- Étape 01 - Alignement Google Flight Deals archive dans `docs/tasks/archive/015-google-flight-deals-alignment.md`.
- Étape 02 - Cause corrigee: recherche locale utilisait `google_flights` avec destination imposee, anciens parametres `100 EUR` / `3-5 nuits`, et filtre retour avant fin de fenetre; elle utilise maintenant `google_flights_deals` destination libre.
- Étape 03 - Parametres Deals visibles et sans secret: `departure_id=NCE`, `outbound_date=2026-07-01,2026-08-31`, `trip_length=1,7`, `max_price=150`, `stops=2`, `currency=EUR`, `gl=fr`, `hl=fr`, `adults=1`, sans `return_date`.
- Étape 04 - Diagnostic `Comparaison Google Flight Deals` disponible avec endpoint, brutes, normalisees, acceptees, rejetees, raison principale, params envoyes, destinations exemples.
- Étape 05 - Smoke reel Deals valide: `30` brutes, `30` normalisees, `28` acceptees, `2` rejetees; STN `44 EUR` et FCO `50 EUR` presents; SVQ absent du global mais probe cible HTTP 200 avec `other=1`.
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
- Écart Google Flight Deals vs local identifié et cadré: les paramètres locaux historiques différaient (`100 EUR`, `3-5 nuits`, endpoint `google_flights` avec destination imposée) alors que la demande utilisateur est `NCE`, `150 EUR`, `1-7 nuits`, `01/07/26-31/08/26`, destination libre, 1 correspondance maximum.
- Correction attendue: provider SerpApi dédié `google_flights_deals`, endpoint distinct `google_flights_deals`, sans `return_date` quand `trip_length` est utilisé, probes ciblés `NCE-SVQ`, `NCE-STN`, `NCE-FCO`.

## Limite

Aucun sweep live large lancé. FlixBus live teste avec `RAPIDAPI_KEY`, mais RapidAPI retourne `403/429` (`You are not subscribed to this API` / `Too many requests`) et aucune offre actionnable n'est récupérée. Playwright reste squelette sûr désactivé par défaut.

## Prochaine tranche

Étape 01 - Si SVQ doit imperativement apparaitre dans la recherche globale, investiguer la decouverte "anywhere" SerpApi/Google Flight Deals: le probe cible trouve NCE-SVQ mais le global ne le renvoie pas dans le top brut.
Étape 02 - Verifier abonnement/quota FlixBus RapidAPI avant nouveau smoke live bus: dernier smoke HTTP `429 Too many requests`.
