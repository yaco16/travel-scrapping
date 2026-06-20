# Google Flight Deals alignment

## Statut

Archive.

## Commits

- Depart : `a3033f545eace38a032f0e32e3adfc0730967dfb`
- Final : reporte dans le compte rendu final apres commit/push.

## Resultats

- Étape 01 - Strategy mise a jour: ecart Google Flight Deals vs local documente, avec anciens parametres locaux differents, endpoint distinct, provider `google_flights_deals`, probes NCE-SVQ/NCE-STN/NCE-FCO.
- Étape 02 - Diagnostics provider enrichis: params publics envoyes sans secret, endpoint, compteurs bruts/normalises/acceptes/rejetes, raison principale, destinations exemples.
- Étape 03 - Provider SerpApi dedie ajoute: `engine=google_flights_deals`, destination libre, `departure_id=NCE`, `outbound_date=2026-07-01,2026-08-31`, `trip_length=1,7`, `max_price=150`, `stops=2`, `currency=EUR`, `gl=fr`, `hl=fr`, `adults=1`, sans `return_date`.
- Étape 04 - Normalisation Deals ajoutee: destination, pays, prix, prix moyen, reduction, dates, aeroports, duree, escales, compagnie, lien, image; persistance avec `run_id`.
- Étape 05 - Filtres alignes: budget inclusif `<= 150 EUR`, depart entre `01/07/26` et `31/08/26`, duree explicite `1-7 nuits`, 1 correspondance maximum.
- Étape 06 - Probes cibles ajoutes en CLI: `google-flight-deals-probes`.
- Étape 07 - Bloc web `Comparaison Google Flight Deals` ajoute.
- Étape 08 - Tests ajoutes/ajustes: params Deals, absence `return_date`, parser fixture Seville/Londres/Rome, persistance `run_id`, affichage web, formats dates/prix.
- Étape 09 - Smoke reel Deals: endpoint `google_flights_deals`; brutes `30`; normalisees `30`; acceptees `28`; rejetees `2`; top prix `STN:44`, `FCO:50`, `PMI:54`, `MLA:71`, `IBZ:71`, `OLB:72`, `AGP:79`, `BOD:80`, `KRK:80`, `CRL:83`; NCE-STN et NCE-FCO presents acceptes; NCE-SVQ absent de la recherche globale.
- Étape 10 - Probes reels cibles: NCE-SVQ HTTP 200 `other=1`; NCE-STN HTTP 200 `other=1`; NCE-FCO HTTP 200 `best=2 other=4`.

## Cause

L'ecart venait de trois causes combinees: endpoint local `google_flights` au lieu de `google_flights_deals`, destination imposee via `arrival_id`, et anciens parametres locaux `100 EUR` / `3-5 nuits`. Un filtre local rejetait aussi les offres dont le retour depassait le 31/08 alors que la contrainte demandee porte sur le depart.

## Validations

- Tests cibles: `48 passed`, puis `46 passed` apres correction parser/filtre.
- Suite integrale: `108 passed`, coverage `89%`.
- Ruff: OK.
- Pyright: `0 errors`.
- Diff check: OK.
- Smoke web: `/search` HTTP 200, `/results` HTTP 200, formulaire affiche `2026-07-01`, `150`, `1-7 nuits`, `1` correspondance; diagnostic Google visible.

## Decision

Tranche terminee. La recherche locale reproduit l'endpoint Google Flight Deals. Si une destination visible Google manque encore en recherche globale mais apparait en probe cible, la cause restante est la decouverte "anywhere" renvoyee par SerpApi/Google, pas les filtres locaux.
