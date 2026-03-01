# QCC real_polaron pack

Contient un index de runs et un mapping explicite pour consommer les CSV issus du repo Polaron.

- qcc_runs_index.csv: 3 runs (N6,N8,N10) basés sur dynamics_N*.csv.
- mapping.json: définitions de Cq, O, R et Sigma.
- raw/: CSV originaux copiés tels quels.

Le workflow `.github/workflows/qcc_polaron_real_smoke.yml` consomme `qcc_runs_index.csv` et produit des artefacts auditables dans `05_Results/qcc_polaron_real_smoke/`.
