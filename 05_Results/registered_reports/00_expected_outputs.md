# Résultats attendus, document d'ancrage

Date: 2026-02-17

## 1. Figures attendues

### Figure 1. 01_evolution_C_seuil.png
Description. Évolution temporelle de C(t) et points de franchissement du seuil sur ΔC(t).  
Format. PNG, dpi 150 minimum.

### Figure 2. 02_effet_intervention.png
Description. Comparaison V(t) avec et sans intervention. Ligne verticale au moment de l'intervention.  
Format. PNG, dpi 150 minimum.

### Figure 3. 03_trajectoires_individuelles.png
Description. Trajectoires de O, R, I dans le temps.  
Format. PNG.

### Figure 4. 04_matrice_correlations.png
Description. Matrice de corrélation entre variables, O, R, I, Cap, Sigma, S, C, V, delta_C.  
Format. PNG.

### Figure 5. 05_bootstrap_ic.png
Description. Distribution bootstrap du moment de détection et intervalle de confiance 95 pourcent.  
Format. PNG.

### Figure 6. 06_analyse_sensibilite.png
Description. Analyse de sensibilité multidimensionnelle.  
Format. PNG.

## 2. Tables attendues

### Table 1. 01_descriptives_phases.csv
Descriptifs par phase, pré seuil, post seuil, post intervention.

### Table 2. 02_tests_causaux.csv
Tests causaux et métriques associées.

### Table 3. 03_robustesse_specifications.csv
Robustesse selon les spécifications alternatives de Cap.

### Table 4. 04_robustesse_parametres.csv
Robustesse selon les paramètres dynamiques et de détection.

### Table 5. 05_bootstrap_quantiles.csv
Quantiles bootstrap sur le moment de détection.

## 3. Règle de validation

Les résultats sont considérés conformes si:
1) au moins un seuil est détecté dans la période d'observation sur un scénario transition
2) l'intervention symbolique produit une baisse de V mesurable et réplicable dans les scénarios prévus
3) les tests de robustesse confirment la stabilité dans plus de 80 pourcent des variantes

Tout écart est documenté et discuté. L'absence de résultat est un résultat.
