# Providers and external APIs

## Classification

| Provider | Classe | Usage | UI principale |
| --- | --- | --- | --- |
| `serpapi_google_flights_deals` | `primary` | Recherche destination libre via Google Flight Deals. Provider avion principal. Appel strict `google_flights_deals`, parser `deals` uniquement. | Oui si clé présente et clé `deals` exploitable. |
| `ryanair` | `primary` | Vols low-cost via `farfnd/v4/roundTripFares`, sans clé. `limit` API plafonné à 20 (voir section dédiée) : au-delà, HTTP 400 et 0 offre. | Oui si activé, pas d'heures de vol (dates seules). |
| `serpapi_google_flights_targeted` | `detail_probe` | Probes ciblés destination+dates via `google_flights`, bornés par configuration, avec `deep_search=true`. Complète Deals sans relâcher les critères. | Oui si clé présente et résultat actionnable. |
| `serpapi_google_flights_airlines` | `detail_probe` | Probes ciblés destination+dates via `google_flights` avec `include_airlines=U2` puis `include_airlines=V7` par défaut. Vise EasyJet/Volotea sans provider direct ni scraping anti-bot. | Oui si clé présente et résultat actionnable. |
| `travelpayouts` | `optional` | Prix indicatifs/cachés. Désactivé si `TRAVELPAYOUTS_MARKER` absent. | Non si marker absent ou aucune offre actionnable. |
| `comparabus` | `optional` | Bus via API publique ComparaBUS: stops, routes, prix, redirect affilié. | Oui seulement si stop non ambigu, route bus, prix et lien redirect explicite. |
| `flixbus` / `flixbus_rapidapi` | `optional` | Bus via RapidAPI. Désactivé par défaut côté UX si `403/429` ou clé/quota inexploitable. | Non si rate-limit/abonnement bloque. |
| `flixbus_openapi` | `optional` | Bus via `global.api.flixbus.com`, sans clé. Résolution ville contrôlée par cache `legacy_id` + autocomplete mobile, jamais par `cities/details` en recherche texte. | Oui seulement si vrais `legacy_id` trouvés sans ambiguïté. |
| `distribusion` | `optional` | Socle bus + train Europe. Désactivé sans credentials/API contractuelle. | Non tant que non configuré. |
| `playwright_probe` | `detail_probe` | Squelette sûr de probe, sans contournement anti-bot. | Non si non configuré. |

## APIs externes étudiées

### Amadeus Flight Offers Search

Intérêt: API structurée, tarifs vols réels, SDK/documentation stables, utile pour requêtes ciblées origine-destination.

Limites: accès clé requis, quotas/sandbox, couverture et prix parfois différents des OTA grand public. La recherche `anywhere` n'est pas le cas nominal: il faut fournir destinations ou construire une liste de destinations candidates.

Utilité projet: intéressante en provider ciblé ou fallback détail, moins adaptée que SerpApi Deals pour destination libre.

### Kiwi/Tequila

Intérêt: API orientée deals, rayon géographique, destination flexible plus naturelle que beaucoup d'APIs vols.

Limites: clé/compte requis, règles commerciales, disponibilité et accès peuvent dépendre du programme partenaire.

Utilité projet: bon candidat futur pour discovery `anywhere`, à tester seulement après stabilisation SerpApi/UI.

### Duffel

Intérêt: API moderne, booking/offer management solide, bonne normalisation.

Limites: accès/validation requis, logique plus orientée vente et parcours de réservation que veille locale. Destination libre non native: il faut itérer sur destinations.

Utilité projet: surdimensionné pour MVP paper-trading; potentiel provider détail si besoin d'offres très structurées.

### Skyscanner Partner API

Intérêt: marque forte, métasearch pertinent, capacités d'inspiration selon accès partenaire.

Limites: accès partenaire non garanti, conditions commerciales, endpoints disponibles variables selon contrat.

Utilité projet: intéressant si accès officiel obtenu; non prioritaire sans partenariat.

### EasyJet / Wizz Air (API interne)

Question testée: existe-t-il, comme pour Ryanair (`farfnd/v4/roundTripFares`, sans clé, HTTP 200 direct), une API interne EasyJet/Wizz Air exploitable sans clé ni contournement anti-bot.

Smoke réel 2026-07-08 (curl, `User-Agent` navigateur standard, aucun contournement anti-bot) :

- Wizz Air : `GET https://be.wizzair.com/7.4.0/Api/search/search` -> HTTP 429 immédiat (rate-limit/anti-bot dès la première requête). `GET https://be.wizzair.com/7.4.0/Api/asset/basic` -> HTTP 404 (version d'API `7.4.0` obsolète ou endpoint inexistant). Page principale `wizzair.com/en-gb` -> HTTP 200 mais HTML livré avec un script de neutralisation de balises `<script>` et détection de bot navigateur (`ua.match(/Googlebot|Bingbot|.../)`), signe d'une protection anti-bot active (type Akamai/PerimeterX) qui bloque le rendu JS normal et donc l'observation des vrais appels API du site.
- EasyJet : `GET https://www.easyjet.com/en` -> HTTP 403 direct. `GET https://www.easyjet.com/api/routepricing/v1/routes` -> HTTP 403. `GET https://www.easyjet.com/ejsi/Areas/Website/Functions/RouteSearch.asmx/GetRoutes` -> HTTP 503, `server: AkamaiNetStorage`. Confirme une protection Akamai active sur le site public, y compris sur d'anciens endpoints `.asmx` legacy.

Constat: contrairement à Ryanair (API `farfnd` publique, sans clé, répond HTTP 200 direct), EasyJet et Wizz Air protègent leur surface HTTP publique par anti-bot (Akamai côté EasyJet, rate-limit + neutralisation JS côté Wizz Air) dès la première requête non-navigateur. Un provider direct de ce type nécessiterait un contournement anti-bot (headless browser, fingerprinting, rotation IP), explicitement hors périmètre (cf. `playwright_probe`: "squelette sûr de probe, sans contournement anti-bot") et contraire à la règle projet de ne pas construire de scraping fragile/instable sur bases non contractuelles.

Décision: ne pas intégrer de provider direct EasyJet/Wizz Air. EasyJet et Volotea passent par `serpapi_google_flights_airlines`, qui interroge `google_flights` avec `include_airlines=U2` et `include_airlines=V7` sur des destinations/dates bornées. Wizz Air reste non ciblé par défaut.

## Bus et train Europe

Le socle technique bus + train existe, mais aucun appel réel Distribusion n'est intégré maintenant.

### ComparaBUS

ComparaBUS fonctionne comme méta-comparateur: recherche de stops, découverte des compagnies par route, récupération des prix par compagnie, puis redirection vers le site marchand. Le provider `comparabus` reproduit ce flux uniquement avec les endpoints publics observés (`/api/stops/departure`, `/api/stops/arrival`, `/api/routes`, `/api/prices`, `/fr/redirect`).

Décision: provider optionnel bus-only, activé par défaut. Aucune offre n'est créée si le stop est ambigu, si aucune route bus n'existe, si le prix manque ou si le champ `link` nécessaire au redirect manque. La confiance reste `medium` car l'API n'est pas contractuelle.

Audit critères 2026-07-09: origine bus volontairement fixe `Nice`; le moteur teste désormais plusieurs paires de dates via `GROUND_MAX_DATE_PAIRS` au lieu de la première paire seulement. La devise envoyée suit `DEFAULT_CURRENCY`; l'affichage final doit rester en EUR ou convertir explicitement avant persistance.

### Distribusion

Recommandation: candidat prioritaire futur pour bus + train Europe.

Intérêt: agrégateur transport terrestre, bus/train, nombreux transporteurs, surface API plus adaptée aux offres terrestres que les probes isolés.

Limite: accès commercial/sandbox et documentation/API contractuelle à obtenir avant toute intégration fiable.

État actuel: provider `distribusion` squelette, désactivé par défaut, visible en diagnostics si bus ou train est demandé, sans appel réseau et sans offres fictives.

Prochaine étape: demander un accès demo/sandbox, puis implémenter l'appel réel Distribusion.

### FlixBus Open API

État actuel: provider `flixbus_openapi` branché et sans clé. Il n'utilise plus `cities/details` comme recherche texte.

Endpoints testés:

- Résolution ville invalide pour recherche texte: `GET https://global.api.flixbus.com/search/service/cities/details?q=Nice&lang=fr`
- Tentative contrôlée de lookup réservation: `GET https://global.api.flixbus.com/mobile/v1/network/autocomplete?q=Nice&limit=50&lang=fr`
- Recherche trajet actuelle: `GET https://global.api.flixbus.com/search/service/v4/search?from_city_id=...&to_city_id=...&departure_date=...&number_adult=1&search_by=cities&currency=EUR`

Constat live 2026-06-20: `cities/details` n'est pas une recherche texte et exige déjà un `from_city_id` ou `to_city_id`. Avec `q=Nice`, `q=Nice Côte d'Azur`, `q=Nice Airport` ou `q=Paris`, l'API répond HTTP 400 avec `At least one of parameters from_city_id and to_city_id should be present.` Le problème n'est pas l'absence générique d'un lookup `city_id`, mais le fait que l'endpoint testé ne permet pas de transformer un nom de ville comme Nice ou Paris en city_id. La recherche trajet attend de vrais `from_city_id`/`to_city_id`; passer `Nice` ou `Paris` provoque HTTP 400 (`Signature "Nice" ... CityId is invalid` ou `invalid from_city_id`).

Smoke réel suivant: autocomplete mobile retourne `legacy_id=6608` et `id=40e13a46-8646-11e6-9066-549f350fcb0c` pour Nice, `legacy_id=2015` et `id=40de8964-8646-11e6-9066-549f350fcb0c` pour Paris. Appeler `/search/service/v4/search` avec les `legacy_id` provoque HTTP 400: `Signature "6608" for class "FlixTech\\SearchService\\Domain\\General\\CityId" is invalid`. Le provider utilise donc par défaut le champ UUID `id` comme `from_city_id`/`to_city_id`; `legacy_id` reste diagnostic ou essai explicite CLI.

Smoke UUID 2026-06-20: `/search/service/v4/search` avec `from_city_id=40e13a46-8646-11e6-9066-549f350fcb0c`, `to_city_id=40de8964-8646-11e6-9066-549f350fcb0c`, `departure_date=30.07.2026`, `products={"adult":1}` retourne HTTP 200, 14 trajets bruts. Aucune offre n'est créée car le payload observé contient prix, dates et opérateur, mais pas de lien réservation explicite.

Décision: aucun city ID n'est inventé. Le provider tente dans l'ordre: cache local `data/cache/flixbus_city_ids.json`, autocomplete mobile, puis recherche trajet seulement si les deux UUID `id` sont présents sans ambiguïté. Le cache stocke séparément `id`, `legacy_id`, `name`, `slug`, `country_code`, `source`, `fetched_at`. Les mappings stockés viennent uniquement de l'autocomplete ou d'un choix manuel CLI (`flixbus-city-cache-set`). Si plusieurs résultats existent, le diagnostic marque `ambiguous` et aucun search trajet n'est appelé. `legacy_id` n'est testé qu'avec `smoke-flixbus-openapi --try-legacy-id`.

Diagnostic utile:

- `flixbus-gtfs-refresh` télécharge explicitement le ZIP officiel.
- `flixbus-gtfs-info` inspecte cache, fichiers GTFS, compteurs et exemples Nice/Paris.
- `flixbus-gtfs-stop-search --query Nice` cherche dans `stops.txt`.
- `flixbus-autocomplete --query Nice` affiche `name`, `id`, `legacy_id`, `slug`, `country_code`.
- `smoke-flixbus-openapi --from Nice --to Paris` affiche GTFS, lookup UUID `id`, `legacy_id`, `id_kind=uuid`, search si IDs présents, compteurs et erreurs. `--try-legacy-id` force un essai legacy séparé.

Alternative recommandée: Distribusion avec accès demo/sandbox et documentation contractuelle pour bus/train Europe.

Audit critères 2026-07-09: `number_adult=1` et `products={"adult":1}` restent fixes par décision produit; `currency` suit `DEFAULT_CURRENCY`; la date de recherche vient des paires générées par les critères et bornées par `GROUND_MAX_DATE_PAIRS`.

### Transitland/GTFS

Utile pour découvrir opérateurs, routes, arrêts et horaires. Pas source de prix ni de réservation.

### FlixBus/FlixTrain GTFS officiel

Source testée: `http://gtfs.gis.flix.tech/gtfs_generic_eu.zip`.

Le GTFS est source officielle réseau/arrêts/lignes/horaires FlixBus/FlixTrain. Il est téléchargé uniquement par commande explicite et stocké dans `data/gtfs/flixbus/gtfs_generic_eu.zip`. Il ne fournit pas forcément les prix ni la réservation. `stop_id` GTFS est un identifiant GTFS: `stop_id GTFS != legacy_id réservation`.

Autocomplete FlixBus mobile: non contractuel, utile pour tenter de récupérer l'UUID `id` et le `legacy_id`, mais pas garanti. Distribusion reste la source recommandée pour API bus/train prix/réservation fiable.

### OSDM

Utile pour le rail, surtout comme standard d'échange. Pour ce MVP, à privilégier via agrégateur au départ avant intégration directe.

## Google Travel Explore

`google_travel_explore` a été testé car l'UI Google Travel Explore affichait des offres visibles alors que `google_flights_deals` ne renvoyait plus de clé `deals` pour NCE été 2026.

Smoke réel SerpApi, endpoint `google_travel_explore`, variantes datées `2026-07-16/2026-07-23`, `2026-07-21/2026-07-28`, `2026-08-28/2026-08-31`, `2026-07-01/2026-07-08`: HTTP 200, `search_metadata.status=Success`, top-level keys `search_metadata`, `search_parameters`, `search_information`, `error`, aucune clé `destinations` ou `flights`, 0 brut, SVQ/STN/FCO absents. Erreur SerpApi: `Empty results for departure_id: "NCE".`

Décision: ne pas intégrer `google_travel_explore` comme provider.

## Ryanair

Provider avion `ryanair` (`travel_scrapping/search/providers/ryanair.py`), sans clé, activé par défaut (`RYANAIR_ENABLED`).

Endpoint: `GET https://services-api.ryanair.com/farfnd/v4/roundTripFares`.

Paramètres envoyés: `departureAirportIataCode`, `outboundDepartureDateFrom/To`, `inboundDepartureDateFrom/To` (bornées par `min_nights`/`max_nights` autour de la fenêtre de recherche), `durationFrom`/`durationTo` (= `min_nights`/`max_nights`, ajoutés pour éviter que l'API renvoie des couples aller/retour hors de la plage de nuits demandée), `language=<default_locale>`, `limit`, `maxPrice`, `offset=0`, `currency`.

**Bug trouvé et corrigé le 2026-07-08** : `limit` était envoyé comme `min(settings.top_results_limit, 100)`, soit 50 par défaut. L'API rejette silencieusement toute valeur de `limit` supérieure à 20 avec `HTTP 400 {"code":"InvalidLimit","message":"Invalid limit"}`. Résultat : **toutes** les requêtes Ryanair échouaient depuis l'ajout du provider (024), donnant 0 offre avion en pratique quel que soit le budget/dates demandés. Vérifié en direct par curl sur l'endpoint réel : `limit<=20` → HTTP 200, `limit>=21` → HTTP 400, quel que soit `maxPrice`/`durationFrom`/`durationTo`. Corrigé par une constante `RYANAIR_MAX_LIMIT = 20` et `limit=min(limit, RYANAIR_MAX_LIMIT)`.

Comportement observé même après correction : sur NCE avec une fenêtre de dates large (ex. 10 juil.-31 août, 1-7 nuits, ≤150€), l'endpoint ne renvoie que quelques offres (`size` dans la réponse, ex. 2), y compris en relâchant `maxPrice` ou en retirant `durationFrom`/`durationTo`. L'endpoint semble renvoyer au plus une poignée de meilleures offres par destination sur toute la fenêtre demandée, pas une liste exhaustive par date — c'est structurel côté API, pas un bug du provider. Ça explique une partie de l'écart avec le nombre d'offres visibles sur l'UI Google Flights (qui agrège bien plus de compagnies/OTA).

Parsing (`_parse_fares`) : `is_direct=True` toujours forcé (Ryanair via cet endpoint est présenté en direct uniquement), pas de correspondance/segment détaillé. Seule la date de départ/retour est disponible (`departureDate`), jamais d'heure — `outbound_departure_at`/`outbound_arrival_at` restent `None` pour ce provider (cf. frise horaire sur les vignettes, qui affiche alors "Horaire non communiqué").

Audit critères 2026-07-09: dates, nuits, budget, devise demandée et langue utilisent les settings. `limit` reste plafonné par `RYANAIR_MAX_LIMIT=20` car limite fournisseur. `adults=1` reste fixe par décision produit.

## Google Flight Deals

Provider avion principal: `serpapi_google_flights_deals`.

Contrat strict:

- `engine=google_flights_deals`
- `departure_id=NCE`
- `type=1`
- `outbound_date=<date début effective>,<date fin effective>` avec début = `max(search_start_date, date courante)` et fin = horizon de recherche configurable (180 jours par défaut)
- `trip_length=1,7`
- `max_price=150`
- `stops=2`
- `currency=EUR`
- `gl=fr`
- `hl=fr`
- `adults=1`
- pas de `return_date` avec `trip_length`

Parsing: clé `deals` uniquement. Si le payload est vide ou sans clé `deals`, aucune offre n'est inventée et aucune observation prix n'est persistée.

Smoke réel 2026-07-09 après correction SerpApi du problème `Fully Empty` sur `departure_id`: HTTP 200, `search_metadata.status=Success`, top-level keys `search_metadata`, `search_parameters`, `departure_informations`, `deals`; `raw_count=30`, `normalized_count=30`, `accepted_count=4`, `rejected_count=26`.

Exemples acceptés observés depuis NCE avec fenêtre effective `2026-07-09,2026-08-31`, 1-7 nuits, <=150 EUR, 1 escale max:

- Cagliari (`CAG`) 13/08/26 -> 20/08/26, 69,00 EUR.
- Djerba (`DJE`) 31/08/26 -> 07/09/26, 149,00 EUR.
- Leeds (`LBA`) 24/07/26 -> 31/07/26, 120,00 EUR.
- Venise (`VCE`) 30/07/26 -> 06/08/26, 60,00 EUR.

Investigation complémentaire 2026-07-09: SerpApi Deals renvoie souvent des offres hors de l'ancienne fin fixe `2026-08-31`. Avec la même requête mais `depart_to=2026-12-31`, le smoke passe de 4 à 25 offres acceptées, sans relâcher budget, nuits ni escales. Le défaut app est donc passé à un horizon glissant de 180 jours.

Les anciennes cibles `SVQ`, `STN`, `FCO` restent absentes de `google_flights_deals`, mais les probes ciblés `google_flights` retrouvent des vols: `SVQ` 1 résultat, `STN` 1 résultat, `FCO` 6 résultats.

Provider complémentaire ajouté: `serpapi_google_flights_targeted`. Il interroge `engine=google_flights` sur un nombre limité de destinations de `config/destinations.yaml` et de paires de dates générées localement, avec `deep_search=true`, `show_hidden=true`, `stops=max_stops+1`, puis laisse les filtres locaux rejeter budget/nuits/dates/escales hors critères. Paramètres de coût: `SERPAPI_TARGETED_ENABLED`, `SERPAPI_TARGETED_MAX_DESTINATIONS`, `SERPAPI_TARGETED_MAX_DATE_PAIRS`. Ce provider ne fait pas de destination libre et ne crée aucune offre si SerpApi ne fournit pas prix, opérateur et booking explicite. `adults=1` reste fixe par décision produit.

## Décision

Décision actuelle: garder `serpapi_google_flights_deals` comme provider avion principal strict. Le problème externe SerpApi `Fully Empty` sur certains `departure_id` est corrigé côté fournisseur pour NCE; continuer à ne parser que `deals` et à ne rien inventer si le payload redevient vide. Aucune nouvelle API bus/train implémentée dans cette tranche.
