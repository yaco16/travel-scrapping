# 019 - Ground transport scaffold

## Statut

Archivee.

## Commits

- Depart: `f95edd12c269c18a0831cab9f9fc529462adbd9a`
- Final: renseigne dans le rapport final apres push.

## Objectif

Preparer le socle bus + train Europe sans appel reel Distribusion tant que credentials et documentation/API contractuelle ne sont pas disponibles.

## Resultats

- Mode `train` ajoute aux schemas, filtres `/results`, onglets, affichage `Train`, API `/deals` et mode `all`.
- Provider `distribusion` ajoute via `DistribusionGroundTransportProvider`, cible bus + train, sans appel reseau et sans offre fictive.
- Settings Distribusion ajoutes et secrets masques: activation, API key, base URL, partner ID.
- Moteur branche `distribusion` pour demandes `bus` ou `train`; provider desactive proprement sans credentials avec `attempted=false`.
- FlixBus RapidAPI reste provider bus secondaire existant.
- Diagnostics fournisseurs affichent `distribusion` desactive et warning `DISTRIBUSION credentials missing` sans secret brut.
- DB compatible: `transport_mode` est deja une string SQLite, aucune migration train necessaire.
- Documentation providers mise a jour: Distribusion prioritaire futur bus + train Europe; Transitland/GTFS pour decouverte, pas prix/reservation; OSDM utile via agregateur au depart.

## Validations

- `pytest tests/test_web.py tests/test_templates.py tests/test_formatters.py`: 35 passed, 1 warning.
- `ruff check .`: No issues found.
- `pyright`: 0 errors, 0 warnings, 0 informations.
- `pytest`: 123 passed, 1 warning.
- `pytest --cov --cov-report=term-missing`: 123 passed, 69 warnings, coverage total 89%.
- `git diff --check`: OK.

## Decision

Aucun appel reel Distribusion sans credentials et API docs contractuelles. Prochaine etape: demander acces demo/sandbox Distribusion, puis implementer l'appel reel.
