# Providers and external APIs

## Classification

| Provider | Classe | Usage | UI principale |
| --- | --- | --- | --- |
| `serpapi_google_flights_deals` | `primary` | Recherche destination libre via Google Flight Deals. Provider principal du projet. | Oui si clé présente et appel exploitable. |
| `google_travel_explore` | `candidate` | Smoke réel Google Travel Explore via SerpApi. Testé comme remplaçant possible de Deals. | Non: smoke NCE été 2026 retourne HTTP 200 `Success` mais `error="Empty results for departure_id: "NCE"."`, 0 liste exploitable. |
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

Décision: ne pas intégrer `google_travel_explore` comme provider principal tant que SerpApi retourne 0 liste exploitable. Garder `serpapi_google_flights_deals` comme provider avion principal/fallback diagnostiqué, sans inventer d'offres. Aucun changement bus/train réel.

## Décision

Priorité actuelle: obtenir une source avion discovery qui retourne une liste exploitable ou clarifier avec SerpApi pourquoi Explore/Deals sont vides pour NCE été 2026. Aucune nouvelle API bus/train implémentée dans cette tranche.
