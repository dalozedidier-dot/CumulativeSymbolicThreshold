# Workflow cleanup

But : réduire la liste affichée dans l'onglet Actions.

Principe : GitHub affiche toute définition YAML présente sous `.github/workflows/` sur la branche par défaut.
On déplace donc les workflows non essentiels vers `.github/workflows_disabled/` (archive) afin qu'ils ne soient plus affichés.

## Utilisation
- Lancez le workflow `Cleanup noisy workflows (one-shot)` via `Run workflow`.
- Il va déplacer automatiquement une liste de workflows "legacy" ou redondants.
- Les fichiers restent disponibles dans `.github/workflows_disabled/` pour restauration manuelle si besoin.

## Workflows conservés (core)
- ci.yml (canonical synthetic suite)
- collector.yml (si présent)
- real_data_smoke.yml
- real_data_matrix.yml
- real_data_canonical_T1_T8.yml
- qcc_canonical_full.yml (si présent)
- qcc_brisbane_stateprob_pipeline.yml
- qcc_polaron_real_smoke.yml
- qcc_real_data_smoke.yml
- symbolic_suite.yml
- t9_diagnostics.yml

Tout le reste est archivé.
