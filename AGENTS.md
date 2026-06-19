@RTK.md
@caveman

# Polymarket Lab — Agent Instructions

RTK se lit depuis `RTK.md` à la racine du projet. Ne pas chercher `/home/yaco/.codex/RTK.md`.

Objectif : construire et mesurer un agent Polymarket en paper trading.

## Sources de vérité

- `docs/strategy/PRODUCT_STRATEGY.md` fixe la stratégie produit stable.
- `docs/strategy/ROADMAP.md` est la source de vérité opérationnelle : architecture validée, état courant, limite et prochaine tranche.
- `TODO.md` contient uniquement les actions immédiates.
- `docs/tasks/active/` contient au maximum une spécification de tranche active.
- `docs/tasks/archive/` contient les rapports finaux, preuves, compteurs, décisions et commits des tranches terminées.
- La mémoire des anciennes conversations n'est jamais une source de vérité.

Ne pas créer de fichier d'état parallèle à `ROADMAP.md`.

## Reprise dans une nouvelle conversation

Lorsqu'un rapport Claude/Codex est collé au début d'une conversation :

1. lire `AGENTS.md` ;
2. lire `docs/strategy/INDEX.md`, puis `docs/strategy/ROADMAP.md` ;
3. lire `TODO.md` ;
4. lire l'archive de la dernière tranche mentionnée dans `ROADMAP.md` ;
5. lire la spécification active seulement si elle existe et concerne la suite.

Comparer le rapport collé au dépôt et aux commits. Ne pas reconstituer tout l'historique.

Répondre exactement avec :

1. analyse ;
2. verdict ;
3. prochaine tranche ;
4. prompt Claude/Codex détaillé dans un writing block.

Le prompt doit conserver les sections utiles : objectif, périmètre, préflight, gates, tests, acceptance, décision, archivage et rapport final.

## Cap produit

Avant toute tranche fonctionnelle, lire :

- `docs/strategy/INDEX.md`
- les documents stratégiques indiqués par cet index
- la spécification active dans `docs/tasks/active/`

Une tranche ne doit pas modifier la stratégie produit sans décision explicite de l'utilisateur.

## Cycle documentaire d'une tranche

Avant le travail :

- créer ou mettre à jour l'unique spécification dans `docs/tasks/active/` ;
- enregistrer le commit de départ, l'objectif, le périmètre, les gates, les tests et les branches de décision.

Après validation :

- remplacer la spécification active par un rapport final dans `docs/tasks/archive/` ;
- renseigner le statut archivé, les commits de départ et final, les résultats, les validations et la décision ;
- supprimer la spécification active ;
- remplacer la section d'état courant de `ROADMAP.md` ;
- réduire `TODO.md` aux seules actions suivantes ;
- ne jamais accumuler l'historique détaillé dans `ROADMAP.md` ou `TODO.md`.


## Règles permanentes — non négociables

### Commits
Chaque tranche DOIT produire des commits sur origin/main avant de rendre
le rapport final. Sans commit pushé, la tranche est incomplète.
Séquence obligatoire :
1. git add -A
2. git commit -m "<tranche>: <description>"
3. git push origin main
4. Vérifier HEAD == origin/main
Reporter les SHAs dans le rapport final. Un rapport sans SHAs de commits
réels est invalide.

### Suite intégrale
La suite intégrale (pytest --cov --cov-report=term-missing) est lancée
manuellement
<!-- dans chaque tranche, sans exception, sans délégation à l'utilisateur. -->
Coverage >= 80 % obligatoire. Reporter n_tests + coverage dans le rapport.
Cette suite intégrale est explicitement autorisée sans chemin de test et sans
condition supplémentaire : `rtk test .venv/bin/python -m pytest --cov --cov-report=term-missing`.

## Validation

Pendant le développement, lancer uniquement les tests ciblés directement liés aux fichiers modifiés.

La validation standard est :

```bash
rtk test .venv/bin/python -m pytest <tests_ciblés>
rtk ruff check <fichiers_python_modifiés>
rtk run '.venv/bin/python -m pyright'
rtk git diff --check
```

Règles :

- Ne jamais lancer `rtk test .venv/bin/python -m pytest` sans chemin de test explicite.
- Exception permanente : la suite intégrale obligatoire ci-dessus se lance sans
  chemin de test explicite dans chaque tranche.
- Lancer uniquement les tests directement affectés par la tranche.
- Si aucun fichier Python n'est modifié, indiquer : `Ruff : non applicable, aucun fichier Python modifié`.


Ajouter ou adapter les tests affectés.

## Git

- Vérifier `rtk git status --short` avant et après le travail.
- Utiliser `rtk git diff --stat` avant un diff complet.
- Ne jamais utiliser `git add .`.
- Stager uniquement les fichiers de la tranche.
- Ne jamais commiter `.env`, SQLite, artefacts temporaires, payloads réseau, secrets ou logs.
- Commit et push uniquement après validations réussies.

## Terminé

Une tranche est terminée lorsque :

- son comportement attendu est implémenté ;
- les tests ciblés passent et la suite intégrale est verte (>= 80 % coverage) ;
- Ruff, Pyright et diff check passent ;
- les invariants de sécurité et SQLite sont respectés ;
- pour une nouvelle verticale ou un nouveau type de pari, le protocole data-first est respecté ou une exception explicite de l'utilisateur est documentée ;
- le rapport final est archivé ;
- `ROADMAP.md` et `TODO.md` sont mis à jour ;
- le commit est poussé ;
- un rapport final court est produit.
