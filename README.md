# Cadre méthodique OSF
Version: v1
Date: 2026-02-17

Ce dépôt contient un cadre méthodique reproductible pour tester l'hypothèse d'un basculement vers un régime symbolique cumulatif, avec architecture O, R, I, viabilité V(t), mismatch Σ(t), stock symbolique S(t), efficacité symbolique s(t), et variable d'ordre C(t).

Structure recommandée pour OSF:
- 01_Theory: noyau théorique et glossaire des variables
- 02_Protocol: protocole, pré-enregistrement, catalogue d'interventions
- 03_Data: dictionnaire de données, règles d'inclusion et exclusion, emplacements raw, processed, synthetic
- 04_Code: environnement, pipeline et scripts
- 05_Results: sorties enregistrées, figures et tables
- 06_Manuscript: manuscrit et annexes méthodes

Notes:
- Tous les paramètres décisionnels doivent être fixés ex ante dans 02_Protocol/PREREG_TEMPLATE.md.
- Les analyses de robustesse sont autorisées mais doivent être identifiées comme secondaires.
