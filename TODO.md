# TODO

## Corrections faites (2026-07-08)

- Commande dev `uvicorn main:app --reload` : ajout d'un shim racine `main.py` qui réexporte `travel_scrapping.main.app` et `create_app`, pour éviter `Could not import module "main"`.
- Bug `search_start_date` figé au 2026-07-01 : provoquait HTTP 400 `outbound_date cannot be in the past` chez SerpApi et Ryanair des que la date reelle depassait cette date figee. `search_start_date` par defaut vaut desormais `date.today()` (`config.py`), et `serpapi_google_flights_deals`/`ryanair`/`amadeus` clampent leur date de depart a `max(search_start_date, today)`.
- Bug agregation bus dans `engine.py` : `row.raw_count`/`row.normalized_count`/`row.error` ne refletaient que la derniere destination testee (ecrasement de l'etat instance provider a chaque destination), masquant les offres/erreurs des autres destinations pour `comparabus` et `flixbus_openapi`. Corrige par accumulation sur toute la boucle destinations.
- Message diagnostic trompeur `flixbus_openapi` : affichait `city_id absent` pour un lookup reussi (ex. Nice) simplement parce qu'il figurait dans les 2 dernieres tentatives ; ne montre plus que les lookups reellement en echec.
- Prix max sans decimales : `max_roundtrip_price_eur` est desormais `int` (plus de `150.0` dans `config_json`/formulaire/diagnostics).
- Checks : `pytest` (suite complete), `ruff check .`, `pyright` (repo entier) tous verts.

## Actions immediates restantes

- Cache `flixbus_city_ids.json` incomplet/errone (trouve par investigation) : sur 20 destinations, `Athens`, `Marrakech`, `Tunis` sans entree cache, et `Malta` mappe a tort vers `Chemult, OR` (bug de selection dans `flixbus_autocomplete.py`, `select_unique_mapping`). Pas encore corrige — a traiter dans une prochaine tranche.
- `flixbus` RapidAPI renvoie `429 Too many requests` : quota externe, rien a corriger cote code aujourd'hui.
- `comparabus` : `HTTP 200 ok=1 raw_count=0` peut aussi refleter un vrai "0 route" par destination (donnee externe), a confirmer apres le fix d'agregation.
- Étape 01 - Smoke live Ryanair : lancer `rtk run '.venv/bin/python -m travel_scrapping.cli search --modes flight'` et verifier resultats dans diagnostics (a refaire avec le fix de date).
- Étape 02 - Creer compte Amadeus sur `developers.amadeus.com`, copier `AMADEUS_CLIENT_ID` + `AMADEUS_CLIENT_SECRET` dans `.env`, smoke live.
- Étape 03 - FlixBus : chercher un lien réservation contractuel pour les résultats OpenAPI ou passer par fournisseur bus contractuel. Garder 0 offre tant qu'aucun lien réservation explicite n'est présent.
- Étape 04 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
