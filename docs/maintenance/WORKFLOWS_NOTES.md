Ce patch ajoute des workflows de donnees reelles par secteur, sans modifier le protocole scientifique.

## Workflows real data par secteur
Chaque workflow est declenche via workflow_dispatch (bouton Run workflow) et produit un artefact contenant:
- logs (run_real_data_demo.log, tests_causaux.log)
- tables (test_timeseries.csv, control_timeseries.csv, summary.json, verdict.json, causal_tests_summary.csv)
- figures (s_t.png, c_t.png, delta_c_t.png)
- meta (sector.txt, dataset.txt, params.txt, rc_demo.txt, rc_causal.txt)

Workflows ajoutes:
- .github/workflows/real_data_smoke_meteo.yml
- .github/workflows/real_data_smoke_trafic.yml
- .github/workflows/real_data_smoke_energie.yml
- .github/workflows/real_data_smoke_economie.yml
- .github/workflows/real_data_smoke_pilot_cpi_monthly.yml (dataset CPI mensuel historique)

## Donnees utilisees
- Pilotes sectoriels: 03_Data/real/<secteur>/pilot_<secteur>/real.csv
- Bundles ORI-C: 03_Data/real/_bundles/data_real_v1/oric_inputs/ et data_real_v2/oric_inputs/

## Pourquoi du YAML
GitHub Actions utilise des fichiers YAML pour decrire les jobs. Les donnees restent des CSV, ces workflows ne changent pas le format des donnees.
