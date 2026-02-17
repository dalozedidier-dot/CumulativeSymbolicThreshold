# Cumulative Symbolic Threshold

[![DOI](https://img.shields.io/badge/DOI-10.17605%2FOSF.IO%2FG62PZ-blue)](https://doi.org/10.17605/OSF.IO/G62PZ)
[![OSF](https://img.shields.io/badge/OSF-G62PZ-lightgrey)](https://osf.io/g62pz/)

Version: v1  
Date: 2026-02-17

Cadre méthodique reproductible pour tester l'hypothèse d'un basculement vers un régime symbolique cumulatif.

Noyau:
1) Cycle interne: Organisation O(t), Résilience R(t), Intégration I(t)  
2) Viabilité: V(t) sur [t-Δ, t], agrégation fixée ex ante  
3) Mismatch: Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t)))  
4) Stock symbolique: S(t)  
5) Efficacité symbolique: s(t) = ΔV(t) / ΔS(t) sous intervention  
6) Variable d'ordre: C(t), gain intergénérationnel attribuable à la transmission sociale sur horizon T  
7) Contrainte exogène: U(t), hausse de demande, baisse de capacité, ou coupure du canal symbolique

Structure:
- 01_Theory
- 02_Protocol
- 03_Data
- 04_Code
- 05_Results
- 06_Manuscript

Démo rapide, cas pré seuil:
```bash
pip install -r 04_Code/requirements.txt
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_minimal.csv --outdir 05_Results
```

Démo rapide, cas avec transition:
```bash
pip install -r 04_Code/requirements.txt
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
```

Tests initiaux:
```bash
pip install -r 04_Code/requirements.txt
pip install -r 04_Code/requirements-dev.txt
PYTHONPATH=04_Code pytest -q
```

OSF:
- DOI: 10.17605/OSF.IO/G62PZ
- URL: https://osf.io/g62pz/

Licence: MIT (voir LICENSE).  
Citation: voir CITATION.cff.
