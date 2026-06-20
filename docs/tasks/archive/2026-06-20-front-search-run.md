# Rapport final - lancement recherche front

## Statut

Archive.

## Commits

- Depart: `7515a6fc43d2afec48da9b805d8b014a8c2810cf`
- Final: commit de tranche pousse sur `origin/main`

## Resultats

- `/search` expose origine, dates depart min/max, nuits min/max, prix max et modes vol/bus.
- Submit front lance le moteur backend existant, cree un `run_id`, puis redirige vers `/results?run_id=...`.
- `/results` filtre par `run_id` quand fourni, sinon conserve dernier run.
- Erreurs providers restent affichees via statuts scrubbes ; FlixBus sans cle/403/429 ne casse pas la page.
- Filtre Jinja `provider_status_display` enregistre.
- `.vscode/` non committe.

## Validations

- `rtk test .venv/bin/python -m pytest tests/test_web.py tests/test_formatters.py` -> 13 passed.
- `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing` -> 73 passed, coverage 82%.
- `rtk ruff check travel_scrapping/web/routes.py travel_scrapping/web/presentation.py travel_scrapping/search/engine.py tests/test_web.py` -> OK.
- `rtk run '.venv/bin/python -m pyright'` -> 0 errors.
- `rtk git diff --check` -> OK.
- Smoke `GET /search`, `POST /run`, `GET /results?run_id=...` -> 200, 303, 200.

## Decision

Tranche terminee. Nouveau run front exploitable sans terminal. Aucun secret ni `.vscode/` commite.
