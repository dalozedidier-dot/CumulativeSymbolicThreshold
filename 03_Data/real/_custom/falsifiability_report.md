# Rapport de falsifiabilite NEP-LIMITE 2.0

Protocole : v1.0.0

> Un modele devient scientifique lorsqu'il expose ce qui pourrait le refuter.

## Principe

Chaque hypothese (H0-H5) et chaque prediction structurelle est associee a :
- une condition de refutation explicite
- un test statistique reproductible
- un seuil de rejet pre-enregistre (non ajustable post hoc)

Un rejet invalide l'hypothese DANS le perimetre teste, pas le cadre entier.

---
## Regime : STABLE

**Tests : 5 | Refutes : 1**

**Verdict : HYPOTHÈSES RÉFUTÉES : PRED_L_EFFECT. Le cadre nécessite une révision sur ces points.**

### H1 -- separation_PO
- Statut : **Non refutee**
- Score : 0.0037 (seuil : 0.6000)
- p-value : 0.820149
- H1 non réfutée : 0% des fenêtres (seuil 80%). Corrélation moyenne = 0.004.

### H2 -- cumulative_E
- Statut : **Non refutee**
- Score : -1.0000 (seuil : 0.0500)
- p-value : 0.500000
- H2 non réfutée : E(t) non stationnaire (ADF p=0.5000). Autocorrélation lag-1 = 0.968.

### H3 -- finite_resilience
- Statut : **Non refutee**
- Score : -1.0895 (seuil : 1.5000)
- p-value : 0.373016
- H3 non réfutée : R_slope=0.0004, E_slope=-0.0220.

### PRED_EMBALLEMENT -- emballement
- Statut : **Non refutee**
- Score : 0.0000 (seuil : 20.0000)
- Aucune conjonction persistante dE>0 & dR<0 détectée.

### PRED_L_EFFECT -- L_effectiveness
- Statut : **REFUTEE**
- Score : -0.0006 (seuil : 0.0500)
- L RÉFUTÉ : réduction moyenne de @(t) = -0.0006 < 0.05. L'opérateur de limite n'a pas d'effet mesurable.

---
## Regime : OSCILLATING

**Tests : 5 | Refutes : 1**

**Verdict : HYPOTHÈSES RÉFUTÉES : PRED_L_EFFECT. Le cadre nécessite une révision sur ces points.**

### H1 -- separation_PO
- Statut : **Non refutee**
- Score : 0.0477 (seuil : 0.6000)
- p-value : 0.013217
- H1 non réfutée : 0% des fenêtres (seuil 80%). Corrélation moyenne = 0.048.

### H2 -- cumulative_E
- Statut : **Non refutee**
- Score : -1.0000 (seuil : 0.0500)
- p-value : 0.500000
- H2 non réfutée : E(t) non stationnaire (ADF p=0.5000). Autocorrélation lag-1 = 0.998.

### H3 -- finite_resilience
- Statut : **Non refutee**
- Score : -0.8041 (seuil : 1.5000)
- p-value : 0.003223
- H3 non réfutée : R_slope=-0.0012, E_slope=-0.0415.

### PRED_EMBALLEMENT -- emballement
- Statut : **Non refutee**
- Score : 0.0000 (seuil : 20.0000)
- Aucune conjonction persistante dE>0 & dR<0 détectée.

### PRED_L_EFFECT -- L_effectiveness
- Statut : **REFUTEE**
- Score : -0.0029 (seuil : 0.0500)
- L RÉFUTÉ : réduction moyenne de @(t) = -0.0029 < 0.05. L'opérateur de limite n'a pas d'effet mesurable.

---
## Regime : BIFURCATION

**Tests : 5 | Refutes : 1**

**Verdict : HYPOTHÈSES RÉFUTÉES : PRED_L_EFFECT. Le cadre nécessite une révision sur ces points.**

### H1 -- separation_PO
- Statut : **Non refutee**
- Score : 0.0516 (seuil : 0.6000)
- p-value : 0.716977
- H1 non réfutée : 0% des fenêtres (seuil 80%). Corrélation moyenne = 0.052.

### H2 -- cumulative_E
- Statut : **Non refutee**
- Score : -1.0000 (seuil : 0.0500)
- p-value : 0.500000
- H2 non réfutée : E(t) non stationnaire (ADF p=0.5000). Autocorrélation lag-1 = 1.000.

### H3 -- finite_resilience
- Statut : **Non refutee**
- Score : -0.1568 (seuil : 1.5000)
- p-value : 0.000000
- H3 non réfutée : R_slope=-0.0198, E_slope=19.6694.

### PRED_EMBALLEMENT -- emballement
- Statut : **Non refutee**
- Score : 0.0000 (seuil : 20.0000)
- Aucune conjonction persistante dE>0 & dR<0 détectée.

### PRED_L_EFFECT -- L_effectiveness
- Statut : **REFUTEE**
- Score : -2.9615 (seuil : 0.0500)
- L RÉFUTÉ : réduction moyenne de @(t) = -2.9615 < 0.05. L'opérateur de limite n'a pas d'effet mesurable.

---
## Seuils pre-enregistres
- H1_correlation_threshold : 0.6
- H1_persistence_window : 30
- H2_stationarity_pvalue : 0.05
- H3_R_unbounded_growth_ratio : 1.5
- H4_unilateral_survival_window : 60
- H4_survival_threshold : 0.8
- regime_prediction_accuracy_min : 0.6
- emballement_E_persistence : 20
- emballement_R_persistence : 20
- emballement_no_transition_window : 60
- ode_residual_r2_min : 0.3
- L_effectiveness_min_reduction : 0.05

---
## Conditions de refutation (resume)

| Hypothese | Condition de refutation | Seuil |
|-----------|----------------------|-------|
| H1 Separation P/O | corr(dP,dO) > 0.60 sur >80% des fenetres | r=0.60, fenetres=30 |
| H2 E cumulatif | E(t) stationnaire (ADF p<0.05) | p=0.05 |
| H3 R finie | E croit ET R croit (ratio>1.5) | ratio=1.5 |
| Emballement | dE>0 & dR<0 persistants SANS transition | accuracy<50% |
| ODE fit | R2 moyen < 0.30 sur donnees reelles | R2=0.30 |
| L effectiveness | @(t) ne diminue pas apres activation L | reduction<0.05 |
| Regime classification | accuracy < 60% | acc=0.60 |