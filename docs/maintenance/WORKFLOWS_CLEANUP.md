# Workflows. Nettoyage et désactivation

Objectif : réduire la liste de workflows visibles dans GitHub Actions sans perdre l'historique.

## Principe
GitHub affiche et exécute uniquement les fichiers `*.yml` / `*.yaml` dans `.github/workflows/`.

Pour désactiver un workflow sans le supprimer :
- on le déplace dans `.github/workflows_disabled/`
- il n'apparaît plus dans l'onglet Actions
- il reste versionné pour référence

## Liste proposée à désactiver (legacy ou redondant)
- full_statistical.yml
- independent_replication.yml
- manual_runs.yml
- nightly_isolated.yml
- sector_bio.yml
- sector_bio_suite.yml
- sector_cosmo.yml
- sector_cosmo_suite.yml
- sector_infra.yml
- sector_infra_suite.yml
- sector_infra_cloud_suite.yml
- sector_social_suite.yml

Raison : ces workflows font doublon avec les pipelines canoniques (matrix, canonical full, real-data) ou sont des variantes isolées.

## Procédure
1. Ajouter ce patch (fichiers tools + docs).
2. Exécuter :
   - `python tools/disable_workflows.py`
3. Commit des suppressions dans `.github/workflows/` + ajouts dans `.github/workflows_disabled/`.

## Après
Workflows qui devraient rester visibles :
- ci.yml
- nightly.yml (si vous gardez un schedule)
- qcc_brisbane_stateprob_pipeline.yml
- qcc_polaron_real_smoke.yml
- qcc_real_data_smoke.yml
- qcc_stateprob_bootstrap.yml (scan-only)
- qcc_stateprob_cross_conditions.yml (scan-only)
- qcc_stateprob_densify_stability.yml (wrapper vers canonique)
- real_data_smoke.yml
- real_data_matrix.yml
- real_data_canonical_T1_T8.yml
- symbolic_suite.yml
- t9_diagnostics.yml
- collector.yml (si présent dans votre branche active)
