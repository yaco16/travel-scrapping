# Rapport final - Resultats, historique, diagnostic

## Statut

Archive.

## Commits

- Depart : 90ac523e654e9ba291231d9586297b4773093627
- Final : renseigne dans le rapport utilisateur apres push.

## Resultats

- Destinations affichees via mapping francais : BTS, VCE, SVQ, BCN.
- Fallback inconnu : `CODE inconnu`.
- Resultats limites aux deals valides du dernier run, nuits recalculees depuis dates.
- Tables Resultats/Historique/Diagnostic scrollables horizontalement.
- Menu principal simplifie : Dashboard, Recherche, Resultats, Historique.
- `/sqlite` conserve en diagnostic local, sans crash sur dates/prix/destination/lien incomplets.
- Prix formates en francais : entier sans decimales, sinon 2 decimales avec virgule.

## Validations

- `rtk test .venv/bin/python -m pytest tests/test_presentation.py tests/test_web.py tests/test_filters.py` : 18 passed.
- `rtk ruff check travel_scrapping/web/presentation.py travel_scrapping/web/routes.py tests/test_presentation.py tests/test_web.py` : OK.
- `rtk run '.venv/bin/python -m pyright'` : 0 errors.
- `rtk git diff --check` : OK.
- `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing` : 42 passed, coverage 83 %.

## Decision

- Pas de suppression de donnees SQLite existantes.
- Les anciennes lignes invalides restent en historique/diagnostic mais ne sont plus affichees dans Resultats.
