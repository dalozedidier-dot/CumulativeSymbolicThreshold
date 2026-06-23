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

## Dedicated novelty workflows

The current CI surface includes the newly added methodological guards:

- `cap_robustness.yml`: runs the executable Cap(t) robustness gate and uploads `cap_robustness_report.json` plus a short Markdown summary. A `CAP_SPEC_SENSITIVE` verdict is treated as a visible scientific result, not as a technical CI crash.
- `replication_bundle.yml`: builds the Zenodo replication bundle, verifies its embedded `BUNDLE_MANIFEST.json`, and can run the ultra-smoke external replication driver.
- `archive_portability.yml`: builds a clean no-git archive and verifies that case-collision checks, data-pack checks and Cap(t) robustness diagnostics also work outside a Git checkout.

The canonical smoke workflow also embeds a Cap(t) robustness report in `ci_canonical_<run_id>` so the summary artifact exposes the new gate alongside the canonical synthetic run.

