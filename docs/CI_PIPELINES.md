# ORI-C . CI pipelines (canonique)

## Principe
Un seul pipeline "canonique full" fait foi. Les autres workflows sont des wrappers qui délèguent via workflow_call.

## Niveaux
- Smoke : validation rapide. Doit rester vert. Contrat de sortie minimal.
- Canonical full : run + stabilité + checks + manifest final.
- Real-data smoke/canonical : exécution sur datasets réels indexés.
- Collector : append-only history.csv + runs_index.csv (post-runs).

## Invariants d'audit par run
Chaque run doit produire :
- contracts/POWER_CRITERIA.json
- contracts/STABILITY_CRITERIA.json
- tables/summary.json
- (si full) stability/stability_summary.json
- manifest.json qui hash les éléments ci-dessus

## Collector
Le collector doit :
- télécharger les artefacts (workflow_run ou schedule)
- parser tous les runs présents
- append-only : ne pas réécrire l'historique
- exporter ci_metrics/history.csv et ci_metrics/runs_index.csv
