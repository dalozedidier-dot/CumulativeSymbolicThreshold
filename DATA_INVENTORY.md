# Inventaire des données — CumulativeSymbolicThreshold

Date : 2026-09-01
Périmètre : `03_Data/`. Aucun CSV n’est remplacé ici.
Règle : un fichier synthétique ou densifié n’est pas une preuve confirmatoire. Voir `docs/EVIDENTIARY_STATUS.md`.

## Ne pas écraser

`03_Data/synthetic/` — fixtures T1–T8 et démos :

- `synthetic_example.csv`
- `synthetic_long_annual.csv`
- `synthetic_long_annual_no_thr.csv`
- `synthetic_minimal.csv`
- `synthetic_test6_s_star.csv`
- `synthetic_with_threshold.csv`
- `synthetic_with_transition.csv`

Ces fichiers restent. On ne les remplace pas par du réel.

## À remplacer ou à étiqueter (priorité)

| Fichier / pilote | Classe | Action |
|---|---|---|
| `03_Data/sector_psych/real/pilot_wvs_synthetic/` | **synthétique dans un dossier `real/`** | premier à sortir de `real/` ou à remplacer par une série WVS observée |
| `sector_cosmo/real/pilot_pantheon_sn/real_densified.csv` | densifié | garder `real.csv` (brut) pour toute preuve ; densifié = exploration seulement |
| `sector_ai_tech/real/pilot_llm_scaling/real_densified.csv` | densifié | idem |
| `sector_bio/real/pilot_pbdb_marine/real_densified.csv` | densifié | idem |
| `examples/notebook_01_synthetic_demo.ipynb` | démo | garder comme démo, pas comme preuve |
| `examples/notebook_03_robustness_analysis.ipynb` | pointe encore sur `synthetic_with_transition.csv` | peut pointer en plus sur un `real.csv` existant (FRED ou GISTEMP) |

Les trois pilotes densifiés sont ceux cités dans `EVIDENTIARY_STATUS.md` (Pantheon ACCEPT fragile, PBDB REJECT, LLM REJECT). Verdicts inchangés ici.

## Déjà réel (ne pas désactiver)

| Secteur | Pilotes utiles |
|---|---|
| `real/fred_monthly/` | `real.csv` + `proxy_spec.json` — pilote économie canonique |
| `sector_climate` | GISTEMP, Mauna Loa, CO2 étendu, climat global |
| `sector_finance` | S&P500, VIX, BTC |
| `sector_cosmo` | `pilot_solar/real.csv` + Pantheon **brut** (`real.csv`) |
| `sector_neuro` | EEG Bonn (`pilot_eeg_bonn/real.csv`) — le zip racine `Epileptic Seizure Recognition.csv.zip` est un doublon |
| `sector_bio` | écologie, épidémie ECDC, excess deaths OWID, PBDB brut |
| `sector_epidemio` | COVID pays (beaucoup de `real.csv` courts) |
| `sector_health` | excess mortality, épidémie BE |
| `sector_seismic` | `pilot_seismic/real.csv` |
| `sector_social` | Twitter AMZN / FB (gros CSV) |
| `sector_infra_cloud` | séries EC2 CPU/disk/net |
| `sector_gdp` | agrégat GDP |

## Doublons à ranger (pas supprimer tant que les scripts pointent dessus)

- Racine `03_Data/` : `ecology_pelt_*`, sea ice NSIDC, `all_ai_models.csv`, `all_redshifts_PVs.csv`, zip EEG — copies ou sources hors `sector_*`.
- Deux arbres : `03_Data/sector_*` **et** `03_Data/real/` (economie / energie / meteo / trafic + bundles v1/v2).
- `03_Data/real/README_REAL_DATA_SECTORS.md` dit déjà que les `real.csv` pilotes économie/énergie/trafic/météo sont des **sélections du bundle LITE**, à remplacer par tes pilotes sectoriels en **gardant le même chemin** pour la CI.

## Simulations (pas des CSV `03_Data/synthetic/`)

Dans `05_Results/` : démo endogène bistable (`full_statistical` sur un **modèle**, pas un pilote réel). Ça reste une démo. Ça ne remplace pas un `real.csv`.

## Prochaine modification de fichiers (quand tu dis oui)

1. Sortir `pilot_wvs_synthetic` de `sector_psych/real/` (renommer le dossier ou le déplacer vers `synthetic/`).
2. Dans `notebook_03`, ajouter un deuxième run sur `03_Data/real/fred_monthly/real.csv` — sans enlever le run synthétique.
3. Pour Pantheon / LLM / PBDB : documenter dans chaque README de pilote que `real_densified.csv` ≠ preuve.
4. Ne pas merger les deux arbres `sector_*` / `real/` tant que `04_Code/` et la CI n’ont pas un seul chemin.
