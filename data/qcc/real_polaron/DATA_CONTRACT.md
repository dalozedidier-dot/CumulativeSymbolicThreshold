# DATA_CONTRACT Polaron-Molecule NISQ (QCC / ORI-C)

Date: 2026-03-02

Source: dépôt GitHub "Unified-Hamiltonian-Simulation-of-the-Polaron-Molecule-Transition-on-a-NISQ-Processor"
Les fichiers bruts sont conservés sans modification dans data/qcc/real_polaron/raw/.

## 1. Fichiers utilisés

### Dynamiques temporelles (candidat Cq(t))
- raw/dynamics_N6.csv
- raw/dynamics_N8.csv
- raw/dynamics_N10.csv

Colonnes attendues:
- Time: temps (unité telle que fournie par la source, ici traitée comme une unité abstraite)
- S(t): signal temporel tel que fourni par la source

Dans ce workflow, Cq(t) est défini par défaut comme Cq(t) = S(t) (sans normalisation implicite).
Toute transformation alternative doit être déclarée dans mapping.json.

### Spectres (proxy O)
- raw/spectrum_N6.csv
- raw/spectrum_N8.csv
- raw/spectrum_N10.csv

Colonnes attendues:
- U_imp: paramètre d'interaction (valeur scalaire répétée par blocs)
- Frequency: fréquence (unité telle que fournie)
- Amplitude: amplitude spectrale

Le workflow sélectionne un bloc U_imp le plus proche de u_imp_target, puis calcule O comme intégrale trapézoïdale de Amplitude sur la bande de fréquences définie.

## 2. Variables QCC utilisées par le workflow

- Cq(t): colonne issue de la dynamique temporelle, par défaut S(t)
- O: exposition, calculée depuis le spectre, constante par run dans ce dataset
- R: régulation, fixée ex ante dans mapping.json. Par défaut R = 0.0
- Sigma(t): cumul discret de max(0, O - R) sur le temps

Ce contrat ne déclare pas de classicité Ccl(t). Aucun calcul de Ccl(t) n'est produit sans répétitions explicites.

## 3. Traçabilité

Chaque run produit:
- tables/timeseries_<run_id>.csv
- tables/events_<run_id>.json
- tables/summary.json
- contracts/mapping.json
- contracts/qcc_runs_index.csv
- contracts/DATA_CONTRACT.md
- figures/*.png
- manifest.json (sha256 de chaque fichier)

Toute mise à jour de mapping.json ou de qcc_runs_index.csv doit être committée. Aucun choix implicite n'est autorisé dans le code.
