# Correction Jinja date_time historique

## Statut

Archive.

## Commits

- Depart : `be24c7affec183b8d3f360f9a783a9a57c73aa31`
- Final : `c08b12a2a048bea3a81978ed67423486dfe8422b`

## Resultats

- Étape 01 - Strategy mise a jour avant code: erreur Jinja `/history`, filtre `date_time` absent selon erreur, smoke `/history` insuffisant, tests compilation templates.
- Étape 02 - Filtre inspecte: `date_time` existe deja dans `travel_scrapping.web.presentation` et est enregistre dans `travel_scrapping.web.routes`; `history.html` reutilise le filtre existant.
- Étape 03 - Test compilation de tous les templates Jinja ajoute via loader reel de `travel_scrapping.web.routes.templates`.
- Étape 04 - Test web reel `/history` renforce: TestClient, exception serveur non masquee, HTTP 200, colonne Date, date `JJ/MM/AA HH:mm`, pas de `None`.
- Étape 05 - Test non-regression filtres Jinja ajoute: `price_display` et `date_time` doivent etre utilises et enregistres.
- Étape 06 - Test historique avec donnees reelles ajoute: ID, Date, Statut, Acceptes, Rejetes, Meilleur prix; ordre `ID / Date / Statut / Acceptes / Rejetes / Meilleur prix`.

## Cause

Le template `travel_scrapping/web/templates/history.html` utilise `{{ run.started_at|date_time }}`. La regression signalee correspond a un environnement Jinja sans filtre `date_time` enregistre; le smoke precedent ne garantissait pas la compilation effective de tous les templates ni le rendu date de `/history`.

## Validations

- `rtk test .venv/bin/python -m pytest tests/test_web.py::test_history_shows_run_start_date_between_id_and_status tests/test_templates.py tests/test_presentation.py::test_date_time_format_handles_missing_datetime_and_iso_values` : 4 passed.
- `rtk test .venv/bin/python -m pytest tests/test_web.py::test_history_shows_run_start_date_between_id_and_status tests/test_templates.py` : 3 passed.
- `rtk ruff check travel_scrapping/web/presentation.py travel_scrapping/web/routes.py tests/test_web.py tests/test_presentation.py tests/test_templates.py` : OK.
- `rtk run '.venv/bin/python -m pyright'` : 0 errors.
- `rtk git diff --check` : OK.
- `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing` : 104 passed, coverage 91%.
- Smoke web reel `/history` : 200, colonne Date rendue, date `20/06/26 09:56`.

## Decision

Tranche terminee apres commit/push. Prochaine action: verifier abonnement/quota FlixBus RapidAPI et budget SerpApi apres decision utilisateur.
