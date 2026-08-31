# Inventaire des données — CumulativeSymbolicThreshold

Date : 2026-09-01  
Branche : `docs/data-inventory-2026-09-01`  
Périmètre : lecture seule de `03_Data/`. Aucun CSV n'est remplacé ici.

Règle ORI-C : un fichier synthétique ou densifié ne peut pas être présenté comme preuve confirmatoire. Le statut évidentiel reste dans `EVIDENTIARY_STATUS.md` / `docs/`.

## Classification

| Classe | Sens | Peut entrer dans une preuve confirmatoire ? |
|---|---|---|
| `real` | Série observée, source citée, pas interpolée pour forcer le seuil | oui, si protocole + manifeste |
| `synthetic` | Généré pour tests T1–T8, smoke, démos | non |
| `densified` / hybride | Série courte réelle étirée / interpolée | non comme preuve canonique |
| `processed` | Dérivé d'une source (z-score, proxy) | dépend de la source |
| `bundle` | Pack versionné v1 / v2 | selon le fichier à l'intérieur |

## Racine `03_Data/`

### Protocoles (garder)

- `README.md`
- `REAL_DATA_COLLECTION_PROTOCOL.md`
- `data_dictionary.md`
- `inclusion_exclusion.md`

### Fichiers à la racine — à classer fichier par fichier

Ces fichiers sont **hors** `synthetic/` et `real/`. Tant qu'ils n'ont pas de manifeste SHA + source, les traiter comme **non canoniques**.

| Fichier | Classe provisoire | Action |
|---|---|---|
| `Epileptic Seizure Recognition.csv.zip` | real candidat (Bonn / UCI) | déplacer vers `real/` + source |
| `N_seaice_extent_*` / `S_seaice_extent_*` | real (NSIDC climatology / daily) | lier au secteur climate |
| `all_ai_models.csv` | à vérifier (souvent agrégat public) | secteur ai_tech |
| `all_redshifts_PVs.csv` | à vérifier | secteur cosmo |
| `ecology_pelt_source.csv` | real source | garder |
| `ecology_pelt_real_oric.csv` | processed | dérivé |
| `ecology_pelt_real_oric_robustz.csv` | processed | dérivé |
| `ecology_pelt_proxy_spec_addon.json` | spec | garder |

## `03_Data/synthetic/` — ne pas remplacer par du réel ici

Ces fichiers servent aux tests. Les garder, ne pas les écraser.

- `synthetic_example.csv`
- `synthetic_long_annual.csv`
- `synthetic_long_annual_no_thr.csv`
- `synthetic_minimal.csv`
- `synthetic_test6_s_star.csv`
- `synthetic_with_threshold.csv`
- `synthetic_with_transition.csv`

## `03_Data/real/` — cœur à privilégier

| Chemin | Rôle |
|---|---|
| `README_REAL_DATA_SECTORS.md` | index secteurs |
| `_bundles/data_real_v1` | bundle versionné v1 |
| `_bundles/data_real_v2` | bundle versionné v2 |
| `_bundles/ORIC_real_data_bundle_LITE_v1_v2` | pack lite |
| `_bundles/bundle_hashes.json` | hashes — ne pas perdre |
| `_bundles/README_BUNDLES.md` | mode d'emploi |
| `_custom/` | séries hors catalogue |
| `_template/` | gabarit nouveau secteur |
| `fred_monthly/` | pilote FRED (canonique déclaré dans le README racine) |
| `pilot_cpi/` | pilote CPI |
| `economie/` `energie/` `meteo/` `trafic/` | secteurs réels |
| `sector_ecology/` `sector_health/` | secteurs réels |
| `registry/` | registre |
| `validation_candidates/` | pas encore canoniques |

## Dossiers `sector_*` à la racine de `03_Data/`

Présents en parallèle de `real/` :

`sector_ai_tech`, `sector_bio`, `sector_climate`, `sector_cosmo`, `sector_ecology`, `sector_epidemio`, `sector_finance`, `sector_gdp`, `sector_health`, `sector_infra`, `sector_infra_cloud`, `sector_neuro`, `sector_psych`, `sector_seismic`, `sector_social`, `sector_stress`

Risque : **double arborescence** (`03_Data/sector_*` et `03_Data/real/sector_*`).  
Action proposée (vague suivante, PR séparée) : un seul index qui dit, pour chaque secteur, où est la série canonique. Ne pas déplacer les fichiers tant que les scripts `04_Code/` / `src/` pointent encore vers les deux.

## `processed/` et `raw/`

- `raw/` : sources avant nettoyage — garder
- `processed/` : sorties pipeline — ne pas confondre avec `real/`

## Ce qu'on ne fait **pas** dans cette PR

- supprimer ou écraser un CSV
- changer un verdict ACCEPT / REJECT
- fusionner les deux arbres `sector_*`
- déclarer un bundle densifié comme preuve confirmatoire

## Prochaine étape (après merge)

1. Pour chaque `sector_*`, ouvrir le dossier et étiqueter `real` / `densified` / `synthetic` dans un tableau court.
2. Les fichiers racine (sea ice, epilepsy zip, redshifts, all_ai_models) reçoivent une fiche source + SHA.
3. Seulement ensuite : proposer un remplacement d'un synthétique de démo par un extrait `real/` **dans les exemples**, jamais dans les fixtures de tests T1–T8.
