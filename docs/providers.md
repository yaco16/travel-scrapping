# Providers and external APIs

## Classification

| Provider | Classe | Usage | UI principale |
| --- | --- | --- | --- |
| `serpapi_google_flights_deals` | `primary` | Recherche destination libre via Google Flight Deals. Provider avion principal. Appel strict `google_flights_deals`, parser `deals` uniquement. | Oui si clé présente et clé `deals` exploitable. |
| `serpapi_google_flights` / `serpapi` | `detail_probe` | Probe ciblé destination précise, pas provider principal pour `anywhere`. | Non, diagnostics avancés seulement. |
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

## Bus et train Europe

Le socle technique bus + train existe, mais aucun appel réel Distribusion n'est intégré maintenant.

### ComparaBUS

ComparaBUS fonctionne comme méta-comparateur: recherche de stops, découverte des compagnies par route, récupération des prix par compagnie, puis redirection vers le site marchand. Le provider `comparabus` reproduit ce flux uniquement avec les endpoints publics observés (`/api/stops/departure`, `/api/stops/arrival`, `/api/routes`, `/api/prices`, `/fr/redirect`).

Décision: provider optionnel bus-only, activé par défaut. Aucune offre n'est créée si le stop est ambigu, si aucune route bus n'existe, si le prix manque ou si le champ `link` nécessaire au redirect manque. La confiance reste `medium` car l'API n'est pas contractuelle.

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

### Transitland/GTFS

Utile pour découvrir opérateurs, routes, arrêts et horaires. Pas source de prix ni de réservation.

### FlixBus/FlixTrain GTFS officiel

Source testée: `http://gtfs.gis.flix.tech/gtfs_generic_eu.zip`.

Le GTFS est source officielle réseau/arrêts/lignes/horaires FlixBus/FlixTrain. Il est téléchargé uniquement par commande explicite et stocké dans `data/gtfs/flixbus/gtfs_generic_eu.zip`. Il ne fournit pas forcément les prix ni la réservation. `stop_id` GTFS est un identifiant GTFS: `stop_id GTFS != legacy_id réservation`.

Autocomplete FlixBus mobile: non contractuel, utile pour tenter de récupérer l'UUID `id` et le `legacy_id`, mais pas garanti. Distribusion reste la source recommandée pour API bus/train prix/réservation fiable.

### OSDM

Utile pour le rail, surtout comme standard d'échange. Pour ce MVP, à privilégier via agrégateur au départ avant intégration directe.

## Google Travel Explore

`google_travel_explore` a été testé car l'UI Google Travel Explore affiche des offres visibles alors que `google_flights_deals` ne renvoie plus de clé `deals` pour NCE été 2026.

Smoke réel SerpApi, endpoint `google_travel_explore`, variantes datées `2026-07-16/2026-07-23`, `2026-07-21/2026-07-28`, `2026-08-28/2026-08-31`, `2026-07-01/2026-07-08`: HTTP 200, `search_metadata.status=Success`, top-level keys `search_metadata`, `search_parameters`, `search_information`, `error`, aucune clé `destinations` ou `flights`, 0 brut, SVQ/STN/FCO absents. Erreur SerpApi: `Empty results for departure_id: "NCE".`

Décision: ne pas intégrer `google_travel_explore` comme provider.

## Google Flight Deals

Provider avion principal: `serpapi_google_flights_deals`.

Contrat strict:

- `engine=google_flights_deals`
- `departure_id=NCE`
- `type=1`
- `outbound_date=2026-07-01,2026-08-31`
- `trip_length=1,7`
- `max_price=150`
- `stops=2`
- `currency=EUR`
- `gl=fr`
- `hl=fr`
- `adults=1`
- pas de `return_date` avec `trip_length`

Parsing: clé `deals` uniquement. Si le payload est vide ou sans clé `deals`, aucune offre n'est inventée et aucune observation prix n'est persistée.

## Décision

Priorité actuelle: clarifier avec SerpApi pourquoi `google_flights_deals` retourne HTTP 200 `Success` sans clé `deals` sur NCE été 2026 alors que Google UI affiche des offres. Aucune nouvelle API bus/train implémentée dans cette tranche.
