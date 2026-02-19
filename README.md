# Cumulative Symbolic Threshold

[![DOI](https://img.shields.io/badge/DOI-10.17605%2FOSF.IO%2FG62PZ-blue)](https://doi.org/10.17605/OSF.IO/G62PZ)
[![OSF](https://img.shields.io/badge/OSF-G62PZ-lightgrey)](https://osf.io/g62pz/)

Version: v1  
Date: 2026-02-17

## Installation

### Conda (recommandé)

```bash
conda env create -f environment.yml
conda activate cumulative_symbolic
```

### Vérification rapide

```bash
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results/demo_transition
python 04_Code/pipeline/run_robustness.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results/robust
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo
python 04_Code/pipeline/tests_causaux.py --outdir 05_Results/ori_c_demo
```

### Données réelles (pilote)

Un point d'entrée est fourni pour exécuter ORI-C sur un CSV réel (proxies O,R,I et optionnellement demand,S), puis lancer les tests causaux.

Exemple rapide (dataset pilote CPI):

```bash
python 04_Code/pipeline/run_real_data_demo.py \
  --input 03_Data/real/pilot_cpi/real.csv \
  --outdir 05_Results/real/pilot_cpi/run_0001 \
  --col-time date --auto-scale --control-mode no_symbolic

python 04_Code/pipeline/tests_causaux.py \
  --run-dir 05_Results/real/pilot_cpi/run_0001 \
  --alpha 0.01 --lags 1-10 --pre-horizon 200 --post-horizon 200 --pdf
```

Guide: `04_Code/pipeline/README_REAL_DATA.md`.


Cadre méthodique reproductible pour tester l'hypothèse d'un basculement vers un régime symbolique cumulatif.

Noyau:
- Cycle interne: Organisation O(t), Résilience R(t), Intégration I(t)
- Viabilité: V(t) sur [t-Δ, t], agrégation fixée ex ante
- Capacité: Cap(O,R,I), forme fixée ex ante
- Mismatch: Σ(t) = max(0, D(E(t)) - Cap(t))
- Stock symbolique: S(t) (proxies de transmission), poids fixés ex ante
- Variable d'ordre: C(t), gain intergénérationnel attribuable à la transmission sociale sur horizon T
- Contrainte exogène: U(t), hausse de demande, baisse de capacité, ou coupure du canal symbolique

Démos incluses:
1) Démo CSV, pré seuil ou transition, basée sur un dataset observé.
2) Démo ORI-C exécutable (Option B), modèle minimal avec scénarios et tests causaux.

Installation:
```bash
pip install -r 04_Code/requirements.txt
```

Démo CSV (pré seuil):
```bash
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_minimal.csv --outdir 05_Results
```

Démo CSV (transition):
```bash
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
```

Démo ORI-C (Option B):
```bash
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo
python 04_Code/pipeline/tests_causaux.py --outdir 05_Results/ori_c_demo
```

Tests initiaux:
```bash
pip install -r 04_Code/requirements-dev.txt
PYTHONPATH=04_Code pytest -q
```

OSF:
- DOI: 10.17605/OSF.IO/G62PZ
- URL: https://osf.io/g62pz/

Licence: MIT (voir LICENSE).  
Citation: voir CITATION.cff.

Démo robustesse (secondaire):
```bash
python 04_Code/pipeline/run_robustness.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
```

## Documents canoniques

- Pancarte ORI-C, version normative 1.0: `01_Theory/ORI_C_Pancarte_Normative_v1_0.md`
