# Cumulative Symbolic Threshold

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

Licence: MIT (voir LICENSE).  
Citation: voir CITATION.cff.
