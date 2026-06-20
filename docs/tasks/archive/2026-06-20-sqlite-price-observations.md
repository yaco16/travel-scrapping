# SQLite price observations

Statut: archive
Commit depart: 51bf102e2a41a2c7eb82cf9d537093f9d20eabce
Commit final: reporte dans le rapport final de session apres push

## Objectif

Corriger l'enregistrement SQLite des observations prix et isoler les anciennes lignes corrompues.

## Resultats

- Insertion `price_observations` protegee par garde sur champs indispensables.
- `run_id` transmis depuis `SearchRun.id`; `accepted_count` base sur observations inserees.
- Diagnostics CLI et web separent observations valides/invalides.
- Variations calculees uniquement sur observations valides.
- CLI `sqlite-clean-invalid --dry-run|--execute` ajoutee pour nettoyage dev local.
- `/results` reste limite aux deals valides du dernier run; historique detail filtre observations invalides.

## Validations

- `rtk test .venv/bin/python -m pytest tests/test_db.py tests/test_cli.py tests/test_web.py tests/test_engine.py`: 14 passed.
- `rtk test .venv/bin/python -m pytest`: 52 passed.
- `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing`: 52 passed, coverage 85%.
- `rtk ruff check .`: OK.
- `rtk run '.venv/bin/python -m pyright'`: OK.
- `rtk git diff --check`: OK.

## Decision

Nettoyer la base locale uniquement apres verification:

```bash
.venv/bin/python -m travel_scrapping.cli sqlite-clean-invalid --dry-run
.venv/bin/python -m travel_scrapping.cli sqlite-clean-invalid --execute
```

Commande de verification apres prochain run:

```bash
.venv/bin/python -m travel_scrapping.cli sqlite-diagnostics
```
