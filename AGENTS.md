@RTK.md
@caveman

# Travel Scrapping - Agent Instructions

RTK se lit depuis `RTK.md` a la racine du projet. Ne pas chercher `/home/yaco/.codex/RTK.md`.

Objectif : MVP local FastAPI pour rechercher et afficher offres de voyage depuis Nice, sans faux resultats.

## Sources de verite

- `docs/strategy/PRODUCT_STRATEGY.md` fixe la strategie produit stable.
- `docs/strategy/ROADMAP.md` fixe l'etat courant, la limite et la prochaine tranche.
- `TODO.md` contient uniquement les actions immediates.
- `docs/tasks/active/` contient au maximum une spec de tranche active.
- `docs/tasks/archive/` contient les rapports finaux.
- La memoire des anciennes conversations n'est jamais source de verite.

Ne pas creer de fichier d'etat parallele a `ROADMAP.md`.

## Debut de requete

Avant d'agir, comprendre l'etat reel du projet depuis les sources de verite, pas depuis la memoire de conversation :

1. lire `AGENTS.md` ;
2. lire `docs/strategy/INDEX.md`, puis `docs/strategy/ROADMAP.md` ;
3. lire `TODO.md` ;
4. lire la spec active dans `docs/tasks/active/` seulement si elle existe et concerne la demande ;
5. lire l'archive mentionnee par `ROADMAP.md` seulement si elle explique le blocage courant.

L'agent doit verifier pourquoi la derniere tentative bloquait avant de coder : restriction fournisseur, quota, secret absent, donnees historiques, diagnostic trompeur, test manquant, dette UI, ou choix produit.

Si la requete utilisateur est trop etroite pour atteindre l'objectif vise, l'agent peut l'elargir prudemment : corriger le bug racine, ajouter diagnostic utile, documenter la restriction, ou proposer la prochaine piste concrete. Ne pas elargir vers un provider/API non valide, un scraping fragile, ou une invention de donnees.

## Memo fin de requete

A la fin de chaque requete utilisateur traitee, mettre a jour le bon memo avant de repondre :

- `TODO.md` : journal court des corrections/investigations recentes, actions immediates restantes, blocages concrets.
- `docs/strategy/ROADMAP.md` : etat courant stable, limite atteinte, prochaine tranche si cela change.
- `docs/tasks/active/` : suivi detaille uniquement pour une tranche active existante.
- `docs/tasks/archive/` : rapport final uniquement quand une tranche est terminee/archivee.

Chaque entree de suivi ajoutee doit indiquer l'agent et rester exploitable par Claude comme par Codex :

```md
## Corrections faites (YYYY-MM-DD, sujet)

- Agent: Codex|Claude.
- Correction: changement effectue ou decision prise.
- Cause racine: pourquoi ca bloquait.
- Restrictions/blocages: limite fournisseur, secret absent, quota, contrat API, dette technique, test impossible.
- Pistes: prochaine amelioration concrete si le probleme n'est pas clos.
- Checks: tests/validations lances, ou raison precise si non lance.
```

Adapter les libelles si c'est une investigation plutot qu'une correction, mais garder `Agent`, `Restrictions/blocages`, `Pistes`, `Checks` quand pertinent.

Ne pas creer de memo parallele. Si rien n'a change cote suivi, ne pas modifier les fichiers et le signaler brievement dans le rapport final.

## Reprise nouvelle conversation

Si un rapport Claude/Codex est colle au debut :

1. lire `AGENTS.md` ;
2. lire `docs/strategy/INDEX.md`, puis `docs/strategy/ROADMAP.md` ;
3. lire `TODO.md` ;
4. lire l'archive de la derniere tranche mentionnee dans `ROADMAP.md` ;
5. lire la spec active seulement si elle existe et concerne la suite.

Repondre avec : analyse, verdict, blocage/restriction identifie, prochaine tranche, prompt Claude/Codex detaille dans un writing block.

## Regles permanentes

- Ne jamais inventer d'offres, prix, providers, routes ou diagnostics.
- Secrets jamais affiches : `.env`, cles API, payloads sensibles.
- SQLite locale : ne pas supprimer ni modifier les donnees hors demande explicite.
- Provider optionnel absent -> app continue avec fallback ou diagnostic propre.
- API/provider live : tests offline par defaut, mocks obligatoires.
- UI utilisateur en francais ; noms fichiers, URLs et classes CSS en anglais.
- Resultats historiques : filtrer avant affichage, ne pas faire confiance aux anciennes lignes stockees.

## Validation

Pendant dev : lancer uniquement tests/checks lies aux fichiers modifies.

Validation standard :

```bash
rtk test .venv/bin/python -m pytest <tests_cibles>
rtk ruff check <fichiers_python_modifies>
rtk run '.venv/bin/python -m pyright'
rtk git diff --check
```

Si aucun Python modifie : `Ruff : non applicable, aucun fichier Python modifie`.

## Git

- Verifier `rtk git status --short` avant commit/push.
- Ne jamais utiliser `git add .`.
- Stager uniquement fichiers de la tranche.
- Ne jamais commiter `.env`, SQLite, caches, logs, couverture ou artefacts temporaires.
- Commit/push seulement apres validations demandees/reussies.
- Travailler uniquement sur main : ne jamais creer de branche ni de worktree. Toute action de creation de branche/worktree doit etre refusee ou signalee au user au lieu d'etre executee.

## Termine

Rapport final court : changements, checks, risques restants.
