# Workflows retirés / désactivés

Ce dossier ne contient plus de workflows YAML exécutables. Les anciens fichiers désactivés ont été supprimés pour éviter la confusion entre workflows actifs, archives et variantes expérimentales.

La surface active est désormais limitée à `.github/workflows/` et documentée dans `docs/CI_PIPELINES.md`.

Anciens workflows retirés lors du nettoyage du 2026-07-02 :

- `full_statistical.yml`
- `independent_replication.yml`
- `manual_runs.yml`
- `nightly_isolated.yml`
- `qcc_brisbane_stateprob_pipeline.yml`
- `qcc_canonical_full.yml`
- `qcc_polaron_real_smoke.yml`
- `qcc_real_data_smoke.yml`
- `qcc_stateprob_bootstrap.yml`
- `qcc_stateprob_cross_conditions.yml`
- `qcc_stateprob_densify_stability.yml`
- `real_canonical_schedule.yml`
- `real_data_canonical_T1_T8.yml`
- `real_data_matrix.yml`
- `real_data_smoke.yml`
- `real_smoke_matrix.yml`
- `repair_ci_metrics.yml`
- `sector_ai_tech_suite.yml`
- `sector_bio.yml`
- `sector_bio_suite.yml`
- `sector_climate_suite.yml`
- `sector_cosmo.yml`
- `sector_cosmo_suite.yml`
- `sector_finance_suite.yml`
- `sector_infra.yml`
- `sector_infra_cloud_suite.yml`
- `sector_infra_suite.yml`
- `sector_psych_suite.yml`
- `sector_social_suite.yml`
- `symbolic_suite.yml`
- `t9_diagnostics.yml`
- `workflow_cleanup.yml`

Pour restaurer un ancien workflow, repartir de l’historique Git plutôt que de garder des YAML dormants dans le dépôt.
