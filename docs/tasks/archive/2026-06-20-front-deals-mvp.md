# Rapport final - Front deals MVP

## Statut

Archive: MVP front exploitable malgre blocage RapidAPI externe.

## Commits

- Depart: `1e4534d9aed0aad27d2dd8ce6b81634d62389d69`
- Final implementation: `653f41f6ca283c0584d5ab7647fec39aa3514ca6`

## Resultats

- `GET /deals` lit SQLite et retourne les offres normalisees du dernier run exploitable.
- Front `/results` affiche destination, dates `JJ/MM/AA`, nuits, prix francais, provider et statut provider.
- Statut FlixBus `403/429` affiche erreur scrubbee (`Too many requests` / `You are not subscribed to this API.`) sans secret et sans crash.
- `.vscode/` ignore du commit.

## Validations

- Tests cibles: `11 passed`.
- Ruff: OK.
- Pyright: OK, `0 errors`.
- Diff check: OK.
- Suite integrale: `71 passed`, coverage `81%`.
- Smoke backend/front: `/results` `200`, `/deals` `200`.

## Decision

RapidAPI non contourne. MVP exploitable cote front via SQLite et diagnostics providers.
