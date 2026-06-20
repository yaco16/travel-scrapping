# Providers and external APIs

## Classification

| Provider | Classe | Usage | UI principale |
| --- | --- | --- | --- |
| `serpapi_google_flights_deals` | `primary` | Recherche destination libre via Google Flight Deals. Provider avion principal. Appel strict `google_flights_deals`, parser `deals` uniquement. | Oui si clé présente et clé `deals` exploitable. |
| `serpapi_google_flights` / `serpapi` | `detail_probe` | Probe ciblé destination précise, pas provider principal pour `anywhere`. | Non, diagnostics avancés seulement. |
| `travelpayouts` | `optional` | Prix indicatifs/cachés. Désactivé si `TRAVELPAYOUTS_MARKER` absent. | Non si marker absent ou aucune offre actionnable. |
| `flixbus` / `flixbus_rapidapi` | `optional` | Bus via RapidAPI. Désactivé par défaut côté UX si `403/429` ou clé/quota inexploitable. | Non si rate-limit/abonnement bloque. |
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

### Distribusion

Recommandation: candidat prioritaire futur pour bus + train Europe.

Intérêt: agrégateur transport terrestre, bus/train, nombreux transporteurs, surface API plus adaptée aux offres terrestres que les probes isolés.

Limite: accès commercial/sandbox et documentation/API contractuelle à obtenir avant toute intégration fiable.

État actuel: provider `distribusion` squelette, désactivé par défaut, visible en diagnostics si bus ou train est demandé, sans appel réseau et sans offres fictives.

Prochaine étape: demander un accès demo/sandbox, puis implémenter l'appel réel Distribusion.

### Transitland/GTFS

Utile pour découvrir opérateurs, routes, arrêts et horaires. Pas source de prix ni de réservation.

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
