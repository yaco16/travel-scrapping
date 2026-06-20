# Archives, historique et diagnostics fournisseurs

## Statut

Archive.

## Commits

- Depart : `42f3765e09d9248417a4bbaced2d1b1faacbcb4c`
- Final : reporte dans le compte rendu final apres push `origin/main`

## Resultats

- Étape 01 - Strategy mise a jour avant code dans `ROADMAP.md`, `TODO.md`, puis tranche archivee.
- Étape 02 - Archives renumerotees de `001-...` a `013-...`, sans suppression de contenu historique.
- Étape 03 - Historique enrichi avec colonne Date issue de `SearchRun.started_at`, format `JJ/MM/AA HH:mm`.
- Étape 04 - Diagnostic absence de resultats inspecte sur DB locale et smoke moteur.
- Étape 05 - Diagnostics fournisseurs visibles: actif, cle, appel tente, HTTP/erreur, brut, normalise, accepte, rejete, raison principale.
- Étape 06 - Cause racine corrigee: SerpApi ne masque plus les offres non actionnables avant filtrage; Travelpayouts est diagnostique meme sans marker; filtre `origin mismatch` ne rejette plus les offres bus.
- Étape 07 - Message "aucune offre" contextualise par compteurs reels.
- Étape 08 - Tests ajoutes/adaptes: archives, strategy, Date historique, formats francais, diagnostics, zero offre, toutes rejetees, offres acceptees, rattachement `run_id`.
- Étape 09 - Validations OK.
- Étape 10 - Commit/push a effectuer apres validations finales.

## Diagnostic reel

- DB locale runs recents 3-8: `completed`, `accepted_count=0`, `rejected_count=0`, `cheapest_price_eur=NULL`.
- Cause historique visible: instrumentation insuffisante et fournisseurs sans offres persistables; SerpApi marquait OK mais les candidats non actionnables etaient filtres dans le provider avant comptage; FlixBus retournait `403/429`; Travelpayouts absent du diagnostic quand `TRAVELPAYOUTS_MARKER` manquait.
- Cause bug fonctionnelle corrigee: les offres bus pouvaient etre rejetees par `origin mismatch` car l'origine bus vaut `Nice` et non `NCE`.

## Smoke moteur

- Run temporaire: `completed`, acceptes `0`, rejetes `3`, meilleur prix `Non disponible`.
- SerpApi: active oui, cle oui, appel oui, HTTP `200`, brutes `4`, normalisees `4`, acceptees `0`, rejetees `3`, raison principale `over budget (3)`.
- Travelpayouts: active non, cle oui, appel non, brutes `0`, normalisees `0`, acceptees `0`, rejetees `0`; marker absent.
- Playwright probe: active non, cle non, appel non, brutes `0`.
- FlixBus: active oui, cle oui, appel oui, HTTP `429`, brutes `0`, normalisees `0`, acceptees `0`, rejetees `0`, erreur `Too many requests`.

## Validations

- `rtk test .venv/bin/python -m pytest tests/test_engine.py tests/test_web.py tests/test_formatters.py tests/test_strategy_docs.py tests/test_db.py` : 31 passed.
- `rtk ruff check ...` : OK.
- `rtk run '.venv/bin/python -m pyright'` : 0 errors.
- `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing` : 101 passed, coverage 91%.
- Smoke web TestClient `/`, `/search`, `/results`, `/history`, `/deals` : 200.
- Smoke moteur temporaire : compteurs ci-dessus.

## Decision

Tranche terminee apres commit/push. Prochaine action: verifier abonnement/quota FlixBus RapidAPI et budget SerpApi avant nouveau sweep live.
