Pack ORI-C . Datasets réels multi-secteurs (sans synthétique)

Objectif
- Fournir un maximum de fichiers CSV testables avec les données fournies.
- Séparation stricte par secteur. Aucun mélange inter-secteurs.
- Priorité aux séries suffisamment longues pour des tests en conditions réelles.

Structure
03_Data/
  sector_bio/
    real/
      pilot_epidemic_ecdc/
        <country>_daily.csv
        <country>_weekly.csv
      pilot_excess_deaths_owid/
        <country>_excess_deaths.csv
      pilot_flu/
        flu_genotype_raw.csv
        flu_genotype_value_counts.csv
        flu_aasequence_features.csv
      pilot_ecology_pelt/
        ecology_pelt_source.csv
        ecology_pelt_real_oric.csv
        ecology_pelt_real_oric_robustz.csv
        ecology_pelt_proxy_spec_addon.json
  sector_stress/
    real/
      pilot_stressEcho/
        stressEcho_raw.csv
        stressEcho_sorted_by_dose.csv
        stressEcho_by_dose_means.csv

Notes
- Les séries ECDC et OWID sont longues (quotidiennes sur plusieurs années) et adaptées aux stress tests.
- Les fichiers flu et stress sont des données réelles mais pas des séries temporelles strictes; ils peuvent être utilisés pour tests de robustesse sur séquences/tabulaires selon ton runner.
- Les fichiers .rda astsa fournis ne sont pas inclus ici car l'environnement ne dispose pas de R pour les extraire.
