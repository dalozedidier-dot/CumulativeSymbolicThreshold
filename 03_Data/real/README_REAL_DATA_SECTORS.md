# ORI-C real data (sector pack)

Ce pack ajoute des fichiers CSV **committables** pour permettre aux workflows CI "real data smoke" de tourner sans erreur de chemin.

## Structure

- 03_Data/real/economie/pilot_cpi/real.csv
- 03_Data/real/energie/pilot_energie/real.csv
- 03_Data/real/trafic/pilot_trafic/real.csv
- 03_Data/real/meteo/pilot_meteo/real.csv

## Provenance

Les fichiers `real.csv` ci-dessus sont des **sélections** issues du bundle `ORIC_real_data_bundle_LITE_v1_v2` (Eurostat, version v2 processed).  
Le bundle d'origine (lite) est conservé sous :

`03_Data/real/_bundles/ORIC_real_data_bundle_LITE_v1_v2/`

## À remplacer par tes pilotes sectoriels

Tu peux remplacer chaque `real.csv` par ton pilote sectoriel réel, en conservant le même chemin pour que le workflow reste stable.
