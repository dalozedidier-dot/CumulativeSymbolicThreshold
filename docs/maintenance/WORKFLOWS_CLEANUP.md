# Workflow cleanup

But : garder l’onglet GitHub Actions lisible et éviter que d’anciens YAML donnent l’impression d’être encore maintenus.

## Décision appliquée le 2026-07-02

- Les workflows actifs ont été renommés avec des noms explicites.
- Les anciens workflows désactivés/legacy ont été supprimés de `.github/workflows_disabled/`.
- La liste des anciens fichiers retirés est conservée dans `.github/workflows_disabled/README.md`.
- Le collector suit maintenant les nouveaux noms/fichiers : `nightly_full_proof.yml` et `qcc_stateprob_full.yml`.

## Surface active attendue

Voir `docs/CI_PIPELINES.md`.
