# Manuscript Draft
Du vivant autonome au regime symbolique cumulatif: architecture O-R-I, seuil de mismatch Sigma, et protocole falsifiable ORI-C

## Abstract
A rediger apres resultats principaux et robustesse.

## 1. Introduction
Ce manuscrit propose un cadre operationnel, falsifiable et preregistrable pour tester une transition de regime entre:
1) un regime viable sans cumul symbolique stable
2) un regime cumulatif ou la transmission sociale produit un gain inter generation, mesurable via C

La cle est de separer:
- le noyau structurel O-R-I -> Cap -> Sigma -> V
- la couche symbolique S -> C, qui peut etre testee sans confondre C avec V quand Sigma est nul

Ce travail vise un point simple: fournir des tests qui claquent. Si un test echoue, il falsifie explicitement une partie du cadre. Les resultats nuls sont acceptes et documentes.

## 2. Theorie
Voir 01_Theory/theory_core.md et la pancarte ORI-C normative.
Le present draft ne modifie pas le cadre. Il fixe un protocole de tests.

## 3. Methodes
Voir 02_Protocol/PROTOCOL_v1.md.
Les tests sont organises en deux blocs:

### 3.1 Noyau ORI
T1 a T3 valident la chaine O-R-I -> Cap -> Sigma -> V sous des interventions de type demand_shock ou capacity_hit.

### 3.2 Regime symbolique cumulatif
T4, T5, T7 valident que S influence C de maniere non triviale:
- T4: variation controlee de S implique une variation de C attribuable a S
- T5: injection symbolique a t0 implique un effet differe sur C a horizon T
- T7: variation progressive de S met en evidence un point de bascule stable S*

Si on veut tester un effet symbolique sur V, il faut volontairement etre en regime Sigma > 0. Sinon V peut rester plat, et le test est mal pose.

## 4. Resultats
A inserer apres execution des scripts dans 05_Results.

## 5. Discussion
Deux hypotheses structurelles motivent ce cadre.

Premiere hypothese: les modeles courants melangent souvent capacite structurelle et transmission symbolique, ce qui rend les tests ambigus.

Seconde hypothese: l absence de protocole preregistrable et falsifiable encourage l interpretation post hoc. Ici, chaque test force une decision locale, puis une aggregation globale.

Cette discussion doit rester ancree dans les sorties des tests. La partie bibliographie sera ajoutee une fois la version preregistrable stabilisee.

## 6. Conclusion
Le cadre ORI-C devient testable par construction, et la validation du regime cumulatif repose sur des preuves minimales cumulatives (T4 + T5 + T7).

Version: draft v0.1
Date: 2026-02-18
Licence: CC BY 4.0
