# ORIC_real_data

Dossier de données réelles pour tests ORI-C.

## Contenu

- raw/
  - Sources brutes (TSV.gz Eurostat) exactement telles que fournies.
  - 14852709.zip (IFSGRID_dataset_20250206.zip) inclus tel quel.

- processed/
  - combined_<GEO>.csv : séries extraites par pays / agrégat.
  - oric_real_panel.csv : panel unique (geo, year) avec toutes les séries.

- oric_inputs/
  - oric_inputs_<GEO>.csv : variables O, R, I, S normalisées sur [0,1] + colonnes O_raw, R_raw, I_raw, S_raw.
  - oric_inputs_panel.csv : panel unique (geo, year) des mêmes variables.

## Séries incluses (extraction ex ante)

- industrial_production_i15 : Industrial production index, industrie totale.
- berd_pc_gdp : Dépenses R&D BERD en % du PIB (quand disponible pour le geo).
- env_tax_env_mio_eur : Taxes environnementales, total, M€.
- ict_spec_pc_ent_ge10 : Part d'entreprises (GE10) avec spécialistes ICT, %.
- solar_collector_ths_m2 : Surface de capteurs solaires, milliers de m².
- heat_pump_cap_ath_mw : Capacité chaleur pompes à chaleur ATH, MW.
- road_elec_ktoe : Consommation électricité transport routier, ktep.
- sdg_13_50_mio_eur : Série SDG 13_50 (unité M€).

## Utilisation rapide

1) Copie ce dossier dans la racine du repo ORI-C.
2) Utilise `oric_inputs/oric_inputs_BE.csv` (ou DE, FR, EE) comme dataset réel de départ.

Astuce: si ton pipeline attend un nom précis de dataset, tu peux copier un fichier vers `data/with_transition.csv`
sans changer le contenu.

## Mise à jour V2

- Ajout des nouveaux TSV.gz dans `raw/`.
- Ajout d'un catalog minimal pour ces nouveaux fichiers dans `catalog/` (dimensions et valeurs échantillonnées).
- Les fichiers `processed/` et `oric_inputs/` ne sont pas recalculés en V2, volontairement, pour garder une base stable.
