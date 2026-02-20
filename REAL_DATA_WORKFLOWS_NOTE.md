# Real data smoke workflows (sectorised)

Ce pack ajoute 4 workflows GitHub Actions séparés par secteur :

- real_data_smoke_economie.yml
- real_data_smoke_energie.yml
- real_data_smoke_trafic.yml
- real_data_smoke_meteo.yml

Chaque workflow exécute 3 datasets :
1) le pilote sectoriel existant (03_Data/real/<secteur>/pilot_*/real.csv) avec mapping explicite des colonnes vers O,R,I
2) le bundle v1 correspondant au même geo (03_Data/real/_bundles/data_real_v1/oric_inputs/oric_inputs_<geo>.csv)
3) le bundle v2 correspondant au même geo (03_Data/real/_bundles/data_real_v2/oric_inputs/oric_inputs_<geo>.csv)

Les artefacts sont toujours uploadés (même si un dataset plante), sous :
_ci_out/real_data_smoke/<secteur>/run_<run_id>/
