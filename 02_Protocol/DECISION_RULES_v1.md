# Règles de décision ORI-C (v1.0, 2026-02-17)

Ce document fixe ex ante les conventions de décision statistiques et les règles d'agrégation des verdicts pour le projet CumulativeSymbolicThreshold.
Il complète PROTOCOL_v1.md. Il est normatif.

## 1. Paramètres globaux fixés ex ante

- Niveau de risque global : alpha = 0.01.
- Intervalle de confiance rapporté : 99 % (1 - alpha).
- Triplet obligatoire par test : p-value, IC 99 %, comparaison au SESOI.
- N_min par condition : 50 runs indépendants (seeds distincts).
- Puissance cible au SESOI : 80 %.
- Gate de puissance : si puissance estimée < 70 % au SESOI, verdict local forcé à INDETERMINATE, même si p <= 0.01.

## 2. SESOI fixés

Les SESOI sont définis une fois pour toutes. Ils ne doivent pas être ajustés après observation.

- Capacité Cap : SESOI_Cap = +10 % relatif à la baseline.
- Viabilité V : SESOI_V = -10 % relatif, mesuré sur un quantile bas (q = 0.05) en fenêtre finale.
- Ordre cumulatif C : SESOI_C = +0.30 écart-type robuste (MAD) par rapport à la baseline.

Notes d'implémentation :
- Pour les effets relatifs, l'effet rapporté est (m2 - m1) / m1.
- Pour l'effet MAD, l'effet rapporté est (m2 - m1) / MAD_baseline.

## 3. Unité d'analyse et résumés temporels

- Une observation indépendante correspond à un run complet identifié par un seed unique.
- Pour les séries, on résume sur une fenêtre finale W.
- Résumés standards :
  - Cap_mean : moyenne de Cap(t) sur le run.
  - A_Sigma : aire cumulée A_Sigma = somme_t Sigma(t).
  - frac_over : proportion de pas avec Sigma(t) > 0.
  - V_q05_post : quantile 0.05 de V(t) sur la fenêtre finale W.
  - C_end : valeur finale de C(t).

## 4. Gate de qualité avant tout verdict

Un run est invalide si au moins un des critères suivants est vrai :
- NaN ou inf dans une métrique résumée.
- Longueur de série incorrecte.
- Colonne requise manquante.

Un test est invalide si au moins un des critères suivants est vrai :
- Moins de N_min runs valides par condition.
- Taux d'échec technique sur la condition > 5 %.

Si un test est invalide, son verdict est INDETERMINATE et il est exclu des agrégations ACCEPT ou REJECT.

## 5. Règles locales de verdict

Pour chaque test, on produit un verdict parmi ACCEPT, REJECT, INDETERMINATE.

- ACCEPT si toutes les conditions sont vraies :
  1) p <= 0.01
  2) IC 99 % exclut 0
  3) effet dans le sens attendu et |effet| >= SESOI
  4) puissance estimée au SESOI >= 70 %

- REJECT si toutes les conditions sont vraies :
  1) p <= 0.01
  2) IC 99 % exclut 0
  3) effet dans le sens opposé et |effet| >= SESOI
  4) puissance estimée au SESOI >= 70 %

- INDETERMINATE sinon.

## 6. Agrégation globale

On sépare deux blocs.

### 6.1 Noyau structurel ORI-Cap-Sigma-V (tests 1 à 3)

- ACCEPT noyau si Test1 = ACCEPT, Test2 = ACCEPT, Test3 = ACCEPT.
- REJECT noyau si au moins un des tests 1 à 3 est REJECT.
- INDETERMINATE sinon.

### 6.2 Couche symbolique S-C (tests 4 à 7)

- ACCEPT symbolique si Test4 = ACCEPT et au moins un parmi Test5, Test6, Test7 = ACCEPT, et aucun REJECT.
- REJECT symbolique si Test4 est INDETERMINATE ou REJECT et au moins un parmi Test5, Test6, Test7 = REJECT.
- INDETERMINATE sinon.

## 7. Artefacts attendus

Les scripts doivent produire au minimum :

- 05_Results/verdicts/verdicts_local.csv
- 05_Results/verdicts/verdicts_global.json
- 05_Results/verdicts/diagnostics.md

Chaque ligne de verdict local contient :
- test_id, condition_a, condition_b
- N_a, N_b
- estimate, effect, sesoi
- p_value, ci_low, ci_high, ci_level
- power_sesoi
- verdict

