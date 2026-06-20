# Rapport final - run front non bloquant

## Statut

Archive.

## Commits

- Depart: `1fbdc6667726dda50d9616387c7c2e9809925c08`
- Final: commit de tranche pousse sur `origin/main`

## Resultats

- `/run` cree immediatement un `SearchRun` en `pending`.
- Le moteur est lance via `FastAPI BackgroundTasks`, puis le run passe `running`, `completed` ou `failed`.
- `/run` redirige vers `/results?run_id=...` sans attendre le moteur.
- `/results` affiche le statut du run, auto-refresh toutes les 5 secondes tant que le run n'est pas terminal, et garde les deals du run visibles.
- Les erreurs de run/provider sont scrubbees avant affichage.
- `/search` desactive le bouton au submit pour limiter le double submit.
- Formats existants conserves: dates JJ/MM/AA, prix francais.
- `.vscode/` non committe.

## Validations

- `rtk test .venv/bin/python -m pytest tests/test_web.py` -> 13 passed.
- `rtk test .venv/bin/python -m pytest tests/test_engine.py tests/test_web.py` -> 15 passed.
- `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing` -> 75 passed, coverage 81%.
- `rtk ruff check travel_scrapping/search/engine.py travel_scrapping/web/routes.py tests/test_web.py` -> OK.
- `rtk run '.venv/bin/python -m pyright'` -> 0 errors.
- `rtk git diff --check` -> OK.
- Smokes: `GET /search` -> 200, `POST /run` -> 303 `/results?run_id=1`, `GET /results?run_id=1` -> 200 avec statut visible.

## Decision

Tranche terminee. Recherche front lancee en tache backend non bloquante.
