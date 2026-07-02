# ORI-C — CI pipelines

## Principe

La surface GitHub Actions doit rester lisible : peu de workflows actifs, des noms explicites, et aucun YAML dormant qui laisse croire qu’un ancien protocole est encore maintenu.

## Workflows actifs

| Fichier | Nom affiché | Rôle | Déclenchement | Statut scientifique |
|---|---|---|---|---|
| `.github/workflows/ci_smoke.yml` | `CI Smoke — Tests + Canonical Fast` | lint, type-check, tests, coverage, canonical fast T1–T8, rapport Cap(t) | push, PR, manuel | signal technique rapide; ne prouve pas le full statistical |
| `.github/workflows/nightly_full_proof.yml` | `Nightly Proof — Full Synthetic + Real Canonical` | full synthetic sans `--fast` + real canonical FRED | quotidien, manuel | workflow de preuve principal |
| `.github/workflows/diagnostic_cap_robustness.yml` | `Diagnostic — Cap(t) Robustness` | test dédié des formes de Cap(t) | push/PR ciblés, manuel | diagnostic méthodologique; `CAP_SPEC_SENSITIVE` n’est pas un crash CI |
| `.github/workflows/real_data_sector_pilots.yml` | `Real Data — Sector Pilots` | 7 pilotes réels par secteurs | push/PR ciblés, manuel | validation pilote, non équivalente au full proof |
| `.github/workflows/qcc_stateprob_full.yml` | `QCC StateProb — Full Diagnostic` | pipeline QCC StateProb complet | manuel | diagnostic spécialisé séparé d’ORI-C canonique |
| `.github/workflows/release_replication_bundle.yml` | `Release — Replication Bundle` | construit et vérifie le bundle de réplication | push/PR ciblés, manuel | packaging/reproductibilité |
| `.github/workflows/integrity_archive_portability.yml` | `Integrity — Archive Portability` | vérifie archive sans `.git`, manifest, datapack, collisions de casse | push/PR ciblés, manuel | hygiène dépôt |
| `.github/workflows/metrics_collector.yml` | `Maintenance — CI Metrics Collector` | collecte les artefacts et alimente `ci_metrics/` | workflow_run, quotidien, manuel | maintenance; ne valide rien seul |

## Règle de lecture

- `CI Smoke` doit être vert rapidement, mais ses artefacts doivent rester étiquetés `smoke_ci`.
- `Nightly Proof` est le seul workflow actif qui peut produire une lecture `full_statistical`, à condition que les gates internes passent réellement.
- `Diagnostic — Cap(t) Robustness` expose la sensibilité de la forme mathématique de Cap(t); un résultat sensible doit être visible, pas masqué.
- Les workflows QCC sont séparés des verdicts ORI-C canoniques pour éviter le mélange des preuves.

## Invariants d’audit par run

Chaque run de preuve doit produire, quand le module concerné s’applique :

- `manifest.json`
- `tables/summary.json` ou équivalent documenté
- fichiers de verdict (`verdict.txt`, `global_verdict.json`)
- logs d’exécution
- artefacts permettant de vérifier les seeds, paramètres et critères de décision

## Workflows retirés

Les anciens workflows désactivés ont été supprimés de `.github/workflows_disabled/` et listés dans `.github/workflows_disabled/README.md`. Cela évite les doublons sectoriels, les workflows one-shot de réparation, et les variantes QCC/real-data devenues ambiguës.
