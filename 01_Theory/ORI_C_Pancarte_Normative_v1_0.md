# Pancarte ORI-C
Version normative 1.0  
Date: 17 février 2026

## CADRE ORI-C
Architecture causale d’un système viable avec potentiel cumulatif symbolique

### 1. Variables internes
Proxies fixés ex ante, indépendants.

- **O(t)** Organisation. Structuration et coordination fonctionnelle.
- **R(t)** Résilience. Absorption et réparation des perturbations.
- **I(t)** Intégration. Cohérence et arbitrage entre composantes.

### 2. Agrégats structurels
Formes fixées ex ante.

- **V(t)** Viabilité. Agrégation non compensatoire sur \\[t-\Delta,\ t\\].
- **Cap(t)** Capacité. Projection explicite \\[
\mathrm{Cap}(t) = O(t) \cdot R(t) \cdot I(t)
\\]  
Forme principale.

### 3. Tension structurelle
- **\Sigma(t)** Mismatch. \\[
\Sigma(t) = \max\bigl(0,\ D(E(t)) - \mathrm{Cap}(t)\bigr)
\\]

### 4. Dimension symbolique
Proxies pondérés ex ante.

- **S(t)** Stock symbolique. Quantité transmissible. Répertoire + codification + densité + fidélité.
- **C(t)** Variable d’ordre. Gain intergénérationnel attribuable à la transmission sociale sur horizon **T**, génétique approximativement constante.

### 5. Contraintes exogènes
- **U(t)** Perturbation externe. Charge, perte de capacité ou coupure symbolique.

### 6. Régimes dynamiques
Opérationnels.

- **Pré-seuil**. C(t) approximativement 0. S(t) non cumulatif.
- **Transition**. Décorrélation partielle O, R, I et C(t).
- **Cumulatif**. C(t) > 0 stable. Amplification symbolique.

### 7. Opérateurs causaux
Fixés ex ante.

- **Mesure**. Proxies vers variables.
- **Agrégation**. Variables vers V(t).
- **Projection**. O, R, I vers Cap(t).
- **Stress**. U(t) vers réponse.
- **Attribution**. S(t) vers C(t).
- **Détection**. \\[
\Delta C(t) > \mu_{\Delta C} + k\,\sigma_{\Delta C} \quad \text{pendant } m \text{ pas consécutifs}
\\]

### 8. Conditions d’audit
Non négociables.

- Tout fixé ex ante.
- Aucun ajustement post-observation.
- Proxies documentés.
- Tests causaux reproductibles.
- Critères de seuil explicites.

## Matrice de tests causaux ORI-C
Version exécutable 1.0

| Test | Manipulation | Variable testée | Succès, preuve minimale | Falsification immédiate |
|---|---|---|---|---|
| T1 | Variation contrôlée O, R, I | Cap(t) | Relation monotone conforme à la forme ex ante | Décorrélation ou inversion |
| T2 | Augmentation contrôlée D(E(t)) | \Sigma(t) | \Sigma(t) > 0 dès que D(E) > Cap(t) | \Sigma(t) = 0 malgré surcharge |
| T3 | Induction de \Sigma(t) élevé | V(t) | Dégradation proportionnelle à \Sigma(t) | V(t) stable malgré \Sigma(t) élevé |
| T4 | Variation contrôlée S(t) | C(t) | Variation de C(t) attribuable à S(t) | C(t) invariant malgré \Delta S(t) significatif |
| T5 | Injection symbolique à t0 | C(t+T) | Effet différé mesurable à horizon T | Absence d’effet différé |
| T6 | Coupure ou forte réduction symbolique | C(t) | Chute de C(t) sans modification de O, R, I | C(t) stable malgré coupure symbolique |
| T7 | Variation progressive de S(t) | C(t) | Apparition d’un point de bascule stable | C(t) strictement linéaire ou continu |
| T8 | U(t) combiné, multi-stress | O, R, I, S, C | Cohérence des relations causales sous stress combiné | Relations instables, inversées ou disparues |

### Preuves minimales cumulatives requises
- **T1 + T2 + T3**. Validité du noyau ORI-Cap-\Sigma-V.
- **T4 + T5 + T7**. Existence d’un régime symbolique cumulatif.
- **T6**. Dimension symbolique non triviale, non réductible à O, R, I.

### Conditions d’exécution
- Tous les proxies, formes fonctionnelles, poids, fenêtres \Delta et T, seuils k et m sont fixés ex ante dans **PREREG_TEMPLATE.md**.
- Aucun recalibrage post-observation.
- Tous les tests reproductibles via seed fixé et pipeline documenté.
- Résultats nuls explicitement acceptés et rapportés.

Cette pancarte et cette matrice sont auto-suffisantes, non circulaires, falsifiables et directement exécutables dans un protocole expérimental ou de simulation.
