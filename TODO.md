# TODO

## Corrections faites (2026-07-08, Travelpayouts marker + deep link Aviasales)

- Utilisateur a obtenu `TRAVELPAYOUTS_TOKEN` et `TRAVELPAYOUTS_MARKER` (compte Travelpayouts, projet "newsletter") et les a renseignés dans `.env`. `INCLUDE_INDICATIVE=true` ajouté aussi (permettait d'activer le provider en mode dégradé avant l'obtention du marker).
- Bug racine identifié en testant en direct avec le vrai token : l'endpoint `v2/prices/latest` de Travelpayouts ne renvoie **jamais** de compagnie aérienne ni de lien de réservation dans son payload (seulement route/prix/dates/`gate` = nom de l'OTA source) — donc toutes les offres étaient rejetées comme non actionables (`missing_fields: booking_url, operator_name`) même une fois le marker présent, car notre code ne construisait aucun lien lui-même.
- Corrigé dans `travelpayouts.py` : nouvelle fonction `build_aviasales_deep_link()` qui construit un vrai lien de recherche Aviasales (`aviasales.com/search/{origin}{ddmm}{destination}{ddmm}1?marker=...`) à partir du marker + route/dates réelles quand le payload ne fournit pas déjà un lien explicite. Quand aucune compagnie n'est communiquée par la source, le `gate` (OTA réel ayant trouvé le prix, ex. "Farera") est utilisé comme `operator_name` avec un warning explicite `"operator is booking site (gate), not confirmed airline"` pour ne pas laisser croire à une compagnie confirmée — conforme à la règle "ne jamais inventer" (donnée réelle de la source, pas fabriquée).
- Test d'isolation corrigé : `tests/test_web.py` utilisait `monkeypatch.delenv("TRAVELPAYOUTS_MARKER")` pour simuler un marker absent, ce qui ne neutralise pas la valeur lue depuis `.env` (pydantic-settings lit `.env` indépendamment de `os.environ`). Remplacé par `monkeypatch.setenv("TRAVELPAYOUTS_MARKER", "")` (2 occurrences) pour une vraie isolation, indépendante du contenu local de `.env`.
- Vérifié en live avec le vrai token + marker : 20 offres brutes reçues, 20 actionables (0 avant), 2 passent tous les filtres prix/nuits/dates du run courant.
- Checks : `pytest` (suite complète), `ruff check` (fichiers modifiés), `pyright` (fichiers modifiés) tous verts.

## Corrections faites (2026-07-08, détails trajet bus)

- Liste résultats bus : la frise affiche maintenant station de départ et station d'arrivée quand le payload source les contient. En cas d'escale avec segments, détail ajouté sous la frise : durée de chaque segment, arrêt d'escale, heure d'arrivée et heure de départ de l'escale.
- Extraction prudente depuis `raw_payload_z` uniquement : aucune station/escale inventée si la source ne fournit pas les segments.
- Correctif suite retour UI : ComparaBUS persiste maintenant les stations résolues dans le payload affichable (`departure_station_name`, `arrival_station_name`, `legs`) pour éviter les codes dans la frise. Si `connection > 0` mais que le fournisseur ne donne pas les segments/arrêts d'escale, l'UI affiche explicitement que les détails d'escale ne sont pas communiqués.
- Présentation escales améliorée : une ligne visuelle par escale avec station, heure d'arrivée, heure de départ, attente, durée du trajet avant et durée du trajet après.
- Checks : `pytest tests/test_bus.py tests/test_presentation.py tests/test_web.py -q`, `ruff check` fichiers modifiés, `pyright`, `git diff --check` verts.

## Corrections faites (2026-07-08, Ryanair zero résultat + frise centrée)

- Bug racine "l'avion ne renvoie aucun résultat" : `RyanairProvider` (`ryanair.py`) envoyait `limit=min(settings.top_results_limit, 100)` (50 par défaut) à `roundTripFares` v4, mais cette API renvoie HTTP 400 `InvalidLimit` dès que `limit > 20` (vérifié en direct par curl : 200 jusqu'à 20, 400 à partir de 21). Toutes les requêtes Ryanair échouaient donc silencieusement. Corrigé : nouvelle constante `RYANAIR_MAX_LIMIT = 20`, `limit=min(limit, RYANAIR_MAX_LIMIT)`. Vérifié en live avec les critères exacts rapportés (NCE, 1-7 nuits, 10 juil-31 août, ≤150€, 1 escale max) : Ryanair passe de HTTP 400/0 résultat à HTTP 200/2 offres réelles.
- Écart restant avec Google Flights (21 offres vs quelques offres ici) : structurel, pas un bug — nos providers actifs sont Ryanair (fare-finder low-cost, réseau limité depuis NCE) et SerpApi `google_flights_deals` (flux "deals" curé, pas une recherche flexible exhaustive comme l'UI Google Flights). Amadeus (clés absentes) et Travelpayouts (marker absent) sont désactivés et combleraient une partie de l'écart une fois configurés (cf. actions restantes).
- Frise horaire (vignette résultats) déplacée au centre géométrique de la carte via `display: grid; grid-template-columns: 1fr auto 1fr` au lieu de ratios flex, qui la faisaient dériver à droite selon la largeur du nom de destination.
- Checks : `pytest` (suite complète), `ruff check .`, `pyright` (repo entier) tous verts.

## Corrections faites (2026-07-08, affichage progressif + frise horaire)

- Affichage progressif : `run_search()` (`engine.py`) n'ecrivait les offres en base qu'une seule fois, tout a la fin, dans une seule transaction — `/results` restait donc vide jusqu'a la fin de la recherche malgre le rafraichissement toutes les 5s. Corrige : nouveau helper `replace_run_deals()` (`db.py`) appele apres chaque lot de provider (vols, Distribusion, chaque provider bus), qui recalcule et commite le meilleur top-N connu a cet instant. Le `<meta http-equiv="refresh">` est remplace par du polling htmx (`hx-trigger="every 2s"` sur `#live-region` dans `results.html`), qui s'arrete automatiquement une fois le run termine. `GET /results` rend desormais toujours la page complete (suppression de la branche `_results_offers.html`-seul sur header `HX-Request`, devenue inutile car `hx-select` decoupe cote client).
- Frise horaire sur chaque vignette (`_deal_timeline.html`, inclus dans `_results_offers.html`) : depart -> escale(s) -> arrivee. Nouveaux champs `outbound_departure_at`/`outbound_arrival_at` sur `DealCandidate`/`Deal` (colonnes nullable ajoutees via `migrate_sqlite`), renseignes uniquement quand la donnee source existe reellement (`Offer.to_deal_candidate()` : depart = `departure_at`, arrivee = `departure_at + duration_minutes`). Seul `comparabus` fournit une heure de depart + duree reelles aujourd'hui ; Ryanair/Amadeus/Travelpayouts n'ont que des dates. La frise degrade proprement vers "Horaire non communique" et n'affiche jamais de duree d'escale inventee (`max_layover_hours` n'est fourni par aucun provider) — conforme a la regle AGENTS.md "ne jamais inventer".
- Verifie manuellement en local (serveur uvicorn + lignes `Deal` injectees) : run pending -> `hx-trigger` present, run terminal -> absent ; offre bus avec heures reelles -> frise avec heures + badge "+1" si arrivee le lendemain ; offre vol sans heure -> "Horaire non communique" sans invention.
- Checks : `pytest` (suite complete, 356 tests), `ruff check .`, `pyright` (repo entier) tous verts.

## Workflow git (2026-07-08)

- Fin du workflow branche/PR : branche `agent/travel-search-fixes` (fixes providers/UI + fix fixture bus) fusionnée directement dans `main` (fast-forward) et poussée. Branche supprimée en local et sur `origin`. Il ne reste que `main`.
- Regle ajoutee dans `AGENTS.md` section Git : travailler uniquement sur `main`, ne jamais creer de branche ni de worktree.

## Corrections faites (2026-07-08, suite)

- Bug "night range mismatch" massif sur les vols (26/41 rejets) : `RyanairProvider` interrogeait `roundTripFares` avec une fenêtre `inboundDepartureDateFrom/To` large (non liée à la date aller precise), et `AmadeusProvider` (Flight Inspiration Search) ne filtre pas du tout la duree du sejour cote API — les deux renvoyaient donc des couples aller/retour hors `[min_nights, max_nights]`, rejetes ensuite par `filters.py`. Corrige : `ryanair.py` envoie desormais `durationFrom`/`durationTo` a l'API ; `amadeus.py` filtre cote client les paires hors bornes dans `_parse_inspire`.
- Bug "9 inconnu" sur les destinations bus : `routes.py` appelait `resolve_airport(deal.destination_airport, ...)` pour tous les deals, y compris bus, alors que `destination_airport` d'un deal bus est un code station Comparabus/FlixBus (pas un code IATA) — la resolution echouait et ecrasait le nom de ville deja connu (`deal.destination_city`, toujours rempli par les providers bus) par `"<code> inconnu"`. Corrige dans `latest_display_deals` et `deal_detail` : pour `transport_mode == "bus"`, utiliser directement `deal.destination_city`.
- UI : `page-hero` compact partagé home/résultats sans doublon de classes, détail deal refondu avec carte prix/CTA, résumé trajet, signaux qualité, warnings lisibles et historique prix sans JSON brut.
- Checks : `pytest tests/providers/test_ryanair.py tests/test_filters.py tests/test_web.py tests/test_bus.py` (76 passed), `ruff check` (fichiers modifies), `pyright` (fichiers modifies) tous verts.

## Corrections faites (2026-07-08)

- Commande dev `uvicorn main:app --reload` : ajout d'un shim racine `main.py` qui réexporte `travel_scrapping.main.app` et `create_app`, pour éviter `Could not import module "main"`.
- Bug `search_start_date` figé au 2026-07-01 : provoquait HTTP 400 `outbound_date cannot be in the past` chez SerpApi et Ryanair des que la date reelle depassait cette date figee. `search_start_date` par defaut vaut desormais `date.today()` (`config.py`), et `serpapi_google_flights_deals`/`ryanair`/`amadeus` clampent leur date de depart a `max(search_start_date, today)`.
- Bug agregation bus dans `engine.py` : `row.raw_count`/`row.normalized_count`/`row.error` ne refletaient que la derniere destination testee (ecrasement de l'etat instance provider a chaque destination), masquant les offres/erreurs des autres destinations pour `comparabus` et `flixbus_openapi`. Corrige par accumulation sur toute la boucle destinations.
- Message diagnostic trompeur `flixbus_openapi` : affichait `city_id absent` pour un lookup reussi (ex. Nice) simplement parce qu'il figurait dans les 2 dernieres tentatives ; ne montre plus que les lookups reellement en echec.
- Prix max sans decimales : `max_roundtrip_price_eur` est desormais `int` (plus de `150.0` dans `config_json`/formulaire/diagnostics).
- Home dashboard : warning setup Amadeus masque comme warning provider non bloquant, bandeau dashboard reduit.
- Checks : `pytest` (suite complete), `ruff check .`, `pyright` (repo entier) tous verts.

## Actions immediates restantes

- Cache `flixbus_city_ids.json` incomplet/errone (trouve par investigation) : sur 20 destinations, `Athens`, `Marrakech`, `Tunis` sans entree cache, et `Malta` mappe a tort vers `Chemult, OR` (bug de selection dans `flixbus_autocomplete.py`, `select_unique_mapping`). Pas encore corrige — a traiter dans une prochaine tranche.
- `flixbus` RapidAPI renvoie `429 Too many requests` : quota externe, rien a corriger cote code aujourd'hui.
- `comparabus` : `HTTP 200 ok=1 raw_count=0` peut aussi refleter un vrai "0 route" par destination (donnee externe), a confirmer apres le fix d'agregation.
- Étape 01 - Smoke live Ryanair : fait, Ryanair renvoie des résultats réels (cf. section du jour). Reste à surveiller si l'API resserre encore la limite.
- Étape 02 - Abandonnee : decision utilisateur (2026-07-08) de ne pas configurer Amadeus, l'API devant etre retiree prochainement. `AmadeusProvider` reste dans le code (desactive faute de cles) mais n'est plus une action a mener.
- Étape 02bis - Travelpayouts : fait (cf. section du jour). Token + marker configures, deep link Aviasales construit cote code, offres actionables en live.
- Étape 03 - FlixBus : chercher un lien réservation contractuel pour les résultats OpenAPI ou passer par fournisseur bus contractuel. Garder 0 offre tant qu'aucun lien réservation explicite n'est présent.
- Étape 04 - Demander acces demo/sandbox `Distribusion` et documentation/API contractuelle.
