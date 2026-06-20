# 020 - Flight regression after ground scaffold

## Statut

Archivee.

## Commits

- Depart: `56b03883907d05fd076fe12ebfb07d6619c3e204`
- Final: reporte dans la reponse finale apres push.

## Objectif

Diagnostiquer et corriger la regression ou une recherche avion NCE ete 2026 affichait `0 offre recue des fournisseurs actifs` apres le scaffold bus/train.

## Resultats

- `parse_modes` retombe toujours sur `flight` si valeur vide, absente ou invalide.
- `all` conserve `flight`, `bus`, `train`.
- `run_search` construit le provider avion quand `flight` est demande et ne le construit pas pour `bus,train` seul.
- Relance home conserve les modes du run, fallback `flight`.
- `/run` retombe sur `flight` si aucun mode n'est envoye.
- Diagnostics `/results` distinguent:
  - aucun provider actif/tente;
  - SerpApi desactive;
  - SerpApi tente avec HTTP non 200;
  - SerpApi tente avec 0 offre brute.
- Diagnostics fournisseurs gardent `serpapi_google_flights_deals` visible avec `attempted`, `http_status`, `raw_count`, `normalized_count`.
- Aucun appel reel Distribusion ajoute.

## Diagnostic reel

Smoke initial et final avec:

- origine `NCE`
- dates `2026-07-01` a `2026-08-31`
- budget `150`
- nuits `1,7`
- correspondance max app `1` / SerpApi `stops=2`
- mode `flight`

Run final: `18`.

SerpApi final:

- enabled: `true`
- key_present: `true`
- attempted: `true`
- http_status: `200`
- raw_count: `0`
- normalized_count: `0`
- accepted_count: `0`
- rejected_count: `0`
- main_rejection_reason: `null`
- deals inserees: `0`

Params publics:

```json
{
  "engine": "google_flights_deals",
  "departure_id": "NCE",
  "type": "1",
  "outbound_date": "2026-07-01,2026-08-31",
  "trip_length": "1,7",
  "max_price": "150",
  "stops": "2",
  "currency": "EUR",
  "gl": "fr",
  "hl": "fr",
  "adults": 1,
  "api_key": "***"
}
```

Constat: l'avion est bien appele avec les parametres attendus, mais SerpApi retourne un payload `Success` sans liste `deals` pour cette config au moment du smoke. `/results?run_id=18` affiche le diagnostic explicite `SerpApi appele, mais 0 offre brute recue.` et garde le provider visible.

## Validations

- `pytest tests/test_web.py tests/test_templates.py tests/test_formatters.py`: 36 passed, 1 warning.
- `ruff check .`: No issues found.
- `pyright`: 0 errors, 0 warnings, 0 informations.
- `pytest`: 128 passed, 1 warning.
- `pytest --cov --cov-report=term-missing`: 128 passed, 86 warnings, coverage total 89%.
- `git diff --check`: OK.

## Decision

Ne pas modifier les parametres SerpApi qui marchaient avant et ne pas integrer Distribusion reel. Le correctif porte sur la selection modes, la preservation UI et le diagnostic. Si SerpApi continue a retourner 0 pour `trip_length=1,7`, investiguer cote API/cache SerpApi ou comparer avec une fenetre plus stricte.
