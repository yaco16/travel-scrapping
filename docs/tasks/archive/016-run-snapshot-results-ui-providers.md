# Run snapshot, results UI and providers rationalization

## Statut

Archive.

## Commits

- Depart : `caf2e8d`
- Final : reporte dans le compte rendu final apres commit/push.

## Resultats

- Étape 01 - Strategy mise a jour pour documenter l'incoherence historique/resultats: run #10 annonce `28` acceptes, `2` rejetes, meilleur prix `44,00 €`, mais `/results` ne listait que 4 lignes.
- Étape 02 - Cause exacte: `/results` utilisait `valid_display_deal(deal, settings)` avec la configuration `.env` courante `100 EUR` / `3-5 nuits`; STN `44,00 €` du run #10 a `7` nuits, donc l'offre etait filtree malgre sa presence en DB et dans l'agregat.
- Étape 03 - `search_runs` stocke maintenant `config_json` et `providers_json`; les nouveaux runs persistent origine, budget, dates, durees, limite, modes/providers et date via `started_at`.
- Étape 04 - Les anciens runs sans snapshot recuperent leur configuration depuis les params provider `serpapi_google_flights_deals`.
- Étape 05 - `/results` affiche les offres acceptees du run, sans reappliquer `.env`, avec tri prix croissant, date depart croissante, destination alphabetique.
- Étape 06 - Compteur visible ajoute: `28 offres affichées sur 28 acceptées`; badge `Meilleur prix` ajoute.
- Étape 07 - Homepage separe configuration par defaut nouvelle recherche et dernier run; dernier run affiche ID, date, statut, config reelle, offres, meilleur prix, `Voir les résultats`, `Relancer avec cette configuration`.
- Étape 08 - CSS homepage/resultats refait selon skill globale `prototype`: hero, cards metriques, tabs, cards resultats, diagnostics repliables, tableaux responsive, mobile.
- Étape 09 - Providers rationalises: `serpapi_google_flights_deals` primary; `serpapi_google_flights`/`serpapi` detail_probe; `travelpayouts` optional masque/desactive sans marker; `flixbus` optional masque si `403/429`; `playwright_probe` diagnostics avances.
- Étape 10 - Note technique APIs ajoutee dans `docs/providers.md`: Amadeus, Kiwi/Tequila, Duffel, Skyscanner Partner API. Aucune API nouvelle implementee.
- Étape 11 - Tests ajoutes: snapshot run vs `.env`, meilleur prix premiere ligne, compteur, homepage dernier run, lien `run_id`, elements UI, providers desactives.
- Étape 12 - Smoke reel: run #11, config `NCE`, `150 EUR`, `01/07/26-31/08/26`, `1-7`, `1` correspondance, destination libre; `28` acceptees, `2` rejetees, meilleur prix STN `44,00 €`, premiere ligne `/results` STN `44,00 €`.

## Validations

- Tests cibles: `28 passed`.
- Suite integrale: `111 passed`, coverage total `89%`.
- Ruff: OK.
- Pyright: `0 errors`.
- Compilation templates: couverte par tests Jinja.
- Smokes web: `/`, `/history`, `/results?run_id=11`, `/deals` HTTP 200.
- Diff check: OK.

## Decision

Tranche terminee. SerpApi Google Flight Deals reste provider principal pour destination libre. Les providers non productifs restent visibles seulement en diagnostics/desactives.
