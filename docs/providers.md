# Providers and external APIs

## Classification

| Provider | Classe | Usage | UI principale |
| --- | --- | --- | --- |
| `serpapi_google_flights_deals` | `primary` | Recherche destination libre via Google Flight Deals. Provider principal du projet. | Oui si clé présente et appel exploitable. |
| `serpapi_google_flights` / `serpapi` | `detail_probe` | Probe ciblé destination précise, pas provider principal pour `anywhere`. | Non, diagnostics avancés seulement. |
| `travelpayouts` | `optional` | Prix indicatifs/cachés. Désactivé si `TRAVELPAYOUTS_MARKER` absent. | Non si marker absent ou aucune offre actionnable. |
| `flixbus` / `flixbus_rapidapi` | `optional` | Bus via RapidAPI. Désactivé par défaut côté UX si `403/429` ou clé/quota inexploitable. | Non si rate-limit/abonnement bloque. |
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

## Décision

Priorité actuelle: fiabiliser `serpapi_google_flights_deals`, snapshot run et UI. Aucune nouvelle API implémentée dans cette tranche.
