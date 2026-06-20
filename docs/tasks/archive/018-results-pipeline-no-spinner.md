# 018 - Results pipeline no spinner

## Statut

Archivee.

## Commits

- Depart: `b1b97523bf3dcc9ea727b584c26e8e1998aebdb3`
- Final: renseigne dans le rapport final apres push.

## Objectif

Retirer les spinners du Pipeline `/results`.

## Resultats

- Spinner retire du template `/results`.
- CSS `.step-spinner` et `@keyframes spin` supprimee.
- `pending` conserve avec `pending-blink`.
- Auto-refresh non terminal conserve.
- Tests adaptes pour verifier absence de `step-spinner`.
- Documentation bus/train clarifiee sans integration Distribusion.

## Validations

- `pytest tests/test_web.py tests/test_templates.py tests/test_formatters.py`: 31 passed, 1 warning.
- `ruff check .`: No issues found.
- `pyright`: 0 errors, 0 warnings, 0 informations.
- `pytest`: 117 passed, 1 warning.
- `pytest --cov --cov-report=term-missing`: 117 passed, 71 warnings, coverage total 89%.
- `git diff --check`: OK.

## Decision

Pas de nouvelle API bus/train maintenant. Distribusion reste candidat prioritaire futur pour bus + train Europe via provider possible `ground_transport_distribusion`, desactive par defaut tant que les credentials sont absents.
