# Checklist mainteneurs et workflows GitHub Actions

Ce document fixe le socle minimal de maintenance pour que le dépôt soit auditable comme paquet Python, comme projet scientifique reproductible et comme pipeline CI.

## Décisions mainteneurs

- Le support Python déclaré doit être unique : Python 3.12 est la cible de référence.
- La vérité des dépendances est `pyproject.toml`.
- `requirements.txt` reste un miroir pratique pour les conteneurs et les scripts historiques, mais ne doit pas diverger du `pyproject.toml`.
- Les console scripts exposés par le paquet doivent appeler des fonctions importables depuis `src/oric`, pas des fichiers externes sous `scripts/`.
- Tout changement de schéma dans `ci_metrics` doit être explicite, documenté et accompagné d’un test.
- Les verdicts affichés comme “current” dans le README doivent pointer vers un artefact daté et immuable.
- Les jeux de données externes doivent avoir une provenance, une licence ou une justification d’usage documentée.
- Une release GitHub doit accompagner les publications de tags destinés à être diffusés.
- Les merges doivent passer par une pull request avec au moins une revue humaine lorsque le changement touche le code, les workflows, les contrats, les données ou les verdicts.

## Workflows ajoutés ou formalisés

| Workflow | Déclencheur | Rôle |
|---|---|---|
| `package.yml` | push, pull_request, manuel | build sdist/wheel, `twine check`, installation depuis wheel, smoke CLI |
| `coverage.yml` | push, pull_request, manuel | deux rapports : `src/oric` et surface exécutable large |
| `dependency-review.yml` | pull_request | blocage des vulnérabilités introduites par dépendances |
| `codeql.yml` | push, pull_request, hebdo, manuel | analyse SAST Python avec CodeQL |
| `secrets.yml` | push, pull_request, manuel | scan complémentaire de secrets |
| `release.yml` | tag `v*`, manuel | build, attestation de provenance, GitHub release, upload artefacts |
| `docs.yml` | changements docs, manuel | build strict de la documentation |

## Flux minimal recommandé

Pull request : tests, lint/typecheck si actif, dependency review, package wheel smoke, coverage split.  
Merge : uniquement après revue et CI verte.  
Hebdomadaire : CodeQL, collecte supply chain, vérification des métriques CI.  
Tag de publication : release GitHub avec artefacts attachés et attestation de provenance.

## Secret scanning

Le workflow `secrets.yml` est un complément. La protection principale doit être activée dans les paramètres GitHub du dépôt : secret scanning et push protection.
