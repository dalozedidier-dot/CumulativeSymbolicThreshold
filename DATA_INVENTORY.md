# Inventaire des données — CumulativeSymbolicThreshold

Date : 2026-09-01
Périmètre : `03_Data/`. Aucun CSV de preuve écrasé.
Règle : synthétique ou densifié ≠ preuve confirmatoire. Voir `docs/EVIDENTIARY_STATUS.md`.

## Fait le 2026-09-01

- **A** — WVS synthétique : `03_Data/synthetic/pilot_wvs_synthetic/`. Ancien dossier `sector_psych/real/pilot_wvs_synthetic/` = renvoi seulement.
- **B** — `examples/notebook_03_robustness_analysis.ipynb` : run synthétique conservé + run FRED.
- **C** — bandeau sur README Pantheon, LLM scaling, PBDB.

## Ne pas écraser — fixtures tests

- `03_Data/synthetic/synthetic_example.csv`
- `03_Data/synthetic/synthetic_long_annual.csv`
- `03_Data/synthetic/synthetic_long_annual_no_thr.csv`
- `03_Data/synthetic/synthetic_minimal.csv`
- `03_Data/synthetic/synthetic_test6_s_star.csv`
- `03_Data/synthetic/synthetic_with_threshold.csv`
- `03_Data/synthetic/synthetic_with_transition.csv`
- `03_Data/synthetic/pilot_wvs_synthetic/` (calibré WVS, pas observé)

## Densifiés — exploration seulement

| Fichier | Brut à privilégier |
|---|---|
| `sector_cosmo/real/pilot_pantheon_sn/real_densified.csv` | `real.csv` |
| `sector_ai_tech/real/pilot_llm_scaling/real_densified.csv` | `real.csv` est déjà SYNTHETIC_CALIBRATED |
| `sector_bio/real/pilot_pbdb_marine/real_densified.csv` | `real.csv` |

## Déjà réel (ne pas désactiver)

FRED mensuel, GISTEMP, Mauna Loa / CO2, S&P500 / VIX, EEG Bonn, COVID / OWID, séismes, EC2, Twitter, GDP, bundle LITE sous `03_Data/real/_bundles/`.

## Doublons (ne pas fusionner tant que la CI pointe les deux)

`03_Data/sector_*` et `03_Data/real/` + fichiers à la racine `03_Data/` (sea ice, zip EEG, pelt).
