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

### 4.1 Présentation des cas contrastés

Deux cas de référence permettent de comprendre le comportement du cadre ORI-C :

**Cas A — Régime pré-seuil (aucune injection symbolique)**
Sans perturbation symbolique, C(t) reste proche de zéro sur la totalité de la série (max_C ≈ −0.004).
Le critère de détection ΔC(t) > μ + 2.5·σ n'est jamais satisfait pendant 3 pas consécutifs.
Verdict T7 : INDETERMINATE (aucun point de bascule détecté).

**Cas B — Régime cumulatif (injection symbolique à t = 30 %)**
Après une injection symbolique à t₀ = 75 (sur 250 pas), C(t) monte progressivement jusqu'à 47.6.
Le critère de détection est satisfait en continu à partir du franchissement du seuil (175/250 pas dépassent le seuil).
Verdict T7 : ACCEPT.

Ces deux cas illustrent la **discontinuité de phase** prédite par H2 : sans injection symbolique, le système ne bascule pas. L'injection crée un régime cumulatif stable, non observable en l'absence de ce canal.

### 4.2 Figures et tables de référence

Les figures suivantes sont disponibles dans `05_Results/demo_figures/figures/` :
- **Fig. 1** (`fig_01_case_A_pre_threshold.png`) — O, R, I, Cap, S, C, ΔC pour le cas A
- **Fig. 2** (`fig_02_case_B_cumulative.png`) — Même variables pour le cas B
- **Fig. 3** (`fig_03_delta_C_threshold.png`) — Comparaison de ΔC(t) avec la ligne de seuil pour les deux cas
- **Fig. 4** (`fig_04_sweep_T7.png`) — Sweep progressif de S : mean C(t) post-injection en fonction du niveau de S

La table de comparaison complète est dans `05_Results/demo_figures/tables/table_01_comparison.csv`.

| Métrique | Cas A | Cas B |
|---------|-------|-------|
| n_steps | 250 | 250 |
| max_C | −0.0044 | 47.61 |
| mean_delta_C | −0.029 | 0.190 |
| n_threshold_exceeded | 1 | 176 |
| max_consecutive_exceeded | 1 | 175 |
| threshold_detected | False | **True** |
| Verdict T7 | INDETERMINATE | **ACCEPT** |

### 4.3 Validation hors échantillon (OOS Panel)

Sur le panel multi-pays (BE, DE, EE, EU27_2020, FR), l'évaluation hors-échantillon (split 2015,
outcome = O) produit :
- Corrélation médiane OOS = 0.503 (> 0 : la tendance linéaire calibrée prédit mieux que la moyenne)
- Trois des cinq pays battent la baseline naïve (BE, EE, EU27_2020)
- Fraction de dépassement du seuil : BE=0.25, EU27_2020=0.12, DE/EE/FR=0.00
- Verdict : **INDETERMINATE** (corr positive mais aucun geo dépasse strictement 25 % de seuil)

### 4.4 Causalité quasi-expérimentale (DiD + Contrôle synthétique)

**Scénario EU27_2020 / O / 2015 (Accord de Paris)**
- ATT = +0.175 (hausse positive post-Accord)
- Bootstrap 99 % CI = [0.096, 0.268] — CI ne contient pas 0
- Parallel trends : p = 0.57 (pente Wald — **plausible**)
- SC : post_gap = 0.077, placebo_p = 0.000 (EU27_2020 est synthétisé uniquement)
- **Verdict : ACCEPT**

**Scénario FR / O / 2010 (choc post-crise financière)**
- ATT = −0.306 (baisse post-GFC pour la France)
- Bootstrap 99 % CI = [−0.390, −0.211] — CI entièrement négatif
- Parallel trends : p = 0.21 (**plausible**)
- SC : post_gap = −0.125, placebo_p = 1.00 (FR n'est pas synthétisé de manière unique)
- **Verdict : REJECT** (France montre une dégradation de O post-2010, résultat cohérent avec une crise structurelle)

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
