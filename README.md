# Cumulative Symbolic Threshold

[![DOI](https://img.shields.io/badge/DOI-10.17605%2FOSF.IO%2FG62PZ-blue)](https://doi.org/10.17605/OSF.IO/G62PZ)
[![OSF](https://img.shields.io/badge/OSF-G62PZ-lightgrey)](https://osf.io/g62pz/)

Version: v1  
Date: 2026-02-17

Cadre méthodique reproductible pour tester l'hypothèse d'un basculement vers un régime symbolique cumulatif.

Noyau:
- Cycle interne: Organisation O(t), Résilience R(t), Intégration I(t)
- Viabilité: V(t) mesurée sur une fenêtre [t-Δ, t], agrégation fixée ex ante
- Mismatch: Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t)))
- Stock symbolique: S(t)
- Efficacité symbolique sous intervention: s(t) = ΔV(t) / ΔS(t)
- Variable d'ordre: C(t), gain intergénérationnel attribuable à la transmission sociale sur un horizon T fixé ex ante
- Intervention exogène: U(t), contrainte extérieure pouvant augmenter D(E(t)), réduire C(O,R,I), ou couper le canal symbolique

Structure:
- 01_Theory: noyau théorique et glossaire
- 02_Protocol: protocole, pré-enregistrement, interventions
- 03_Data: dictionnaire de données, règles d'inclusion et exclusion, exemples
- 04_Code: environnement minimal et pipeline de calcul
- 05_Results: sorties et figures
- 06_Manuscript: manuscrit et annexes méthodes

Démo rapide:
- Données synthétiques minimales: 03_Data/synthetic/synthetic_minimal.csv
- Script: 04_Code/pipeline/run_synthetic_demo.py
- Sorties attendues: 05_Results/figures/ (2 PNG) et 05_Results/tables/processed_synthetic.csv

OSF:
- DOI du projet: 10.17605/OSF.IO/G62PZ
- URL OSF: https://osf.io/g62pz/

Licence: MIT (voir LICENSE).  
Citation: voir CITATION.cff.
