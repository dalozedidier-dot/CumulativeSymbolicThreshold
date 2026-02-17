# PROTOCOL v1

Version: v1  
Date: 2026-02-17

## 1. Objet
Tester un basculement vers un régime symbolique cumulatif.

## 2. Hypothèses et falsification
H1 Activation:
Le cycle externe s'active si Σ(t) > Σ* pendant au moins τ.

Falsification H1:
Activation observée alors que Σ(t) ≤ Σ* presque partout.

H2 Basculement:
C(t) montre un changement de régime détectable et robuste.

H3 Causalité:
Perturber le canal symbolique dégrade V(t) de façon réplicable dans le régime cumulatif.

H4 Hystérésis:
Le retour au régime pré seuil exige une diminution plus forte des paramètres que celle du franchissement.

## 3. Variables
Cap(t) = Cap(O,R,I), forme fixée ex ante.  
Σ(t) = max(0, D(E(t)) - Cap(t)).  
S(t) et C(t) définis ex ante.

## 4. Critère principal de seuil
ΔC(t) = C(t) - C(t-1)

Seuil franchi si:
ΔC(t) > μ_ΔC + k·σ_ΔC pendant m pas consécutifs.

## 5. Contraintes exogènes U(t)
Définir U(t) et la mesurer si plausible.

Trois voies:
- hausse de demande
- baisse de capacité
- coupure du canal symbolique

Test causal:
Comparer avec versus sans U(t) sur V(t), C(t) et signatures.

## 6. Designs
Simulation, expérimental, quasi expérimental, séries instrumentées.

## 7. Reproductibilité
Seeds, versions, journal de run, données minimales.

## 8. Robustesse

### 2.7.4 Tests de robustesse

Pour garantir que les résultats ne dépendent pas de choix arbitraires de spécification, nous réaliserons une série de tests de robustesse systématiques. Ces tests sont secondaires et non décisionnels. Ils ne modifient pas les critères de décision des hypothèses H1 à H4.

#### 1. Spécifications alternatives de Cap(O,R,I)

Objectif. Vérifier que la détection de mismatch et les inférences causales ne dépendent pas d'une forme fonctionnelle particulière de l'agrégation des observables.

Variantes testées.
- Cap1. Moyenne simple pondérée, spécification principale. Cap = w_O·O + w_R·R + w_I·I avec w_O = 0.4, w_R = 0.35, w_I = 0.25.
- Cap2. Pondérations alternatives. w_O = 0.5, w_R = 0.3, w_I = 0.2. Puis w_O = 0.33, w_R = 0.33, w_I = 0.34.
- Cap3. Produit pondéré, interactions. Cap = O^a · R^b · I^c avec a, b, c renormalisés.
- Cap4. Minimum des trois composantes. Cap = min(O, R, I).
- Cap5. Agrégation non linéaire avec saturation. Cap = s · (1 - exp(-(w_O·O + w_R·R + w_I·I)/h)) avec s et h fixés ex ante.

Critère de robustesse. Les seuils sont détectés aux mêmes périodes à plus ou moins 5 pourcent de la chronologie et les effets causaux conservent le même signe directionnel.

#### 2. Paramètres de dynamique ORI C

Objectif. Tester la sensibilité aux coefficients de stockage et d'érosion dans la dynamique S et C.

Plages testées, avec pas de 0.05 ou 0.1 selon charge de calcul.
- alpha_sigma_to_S, conversion Sigma vers S. Plage [0.05, 0.15] autour de 0.08.
- beta_S_to_C, conversion S vers C. Plage [0.03, 0.09] autour de 0.06.
- S_decay et C_decay. Plages [0.0, 0.05] autour des valeurs nominales.

Critère de robustesse. Présence de la structure de phases, pré seuil, franchissement, post intervention, dans au moins 80 pourcent des combinaisons.

#### 3. Fenêtres temporelles

Objectif. Vérifier que la détection de seuil n'est pas un artefact de la taille de fenêtre choisie.

Fenêtres testées.
- fenêtre w pour mu et sigma dans la détection. w ∈ {5, 10, 15, 20}.
- paramètre k. k ∈ {2.0, 2.5, 3.0, 3.5}.
- m, nombre de pas consécutifs. m ∈ {2, 3, 4}.

Critère de robustesse. Corrélation supérieure à 0.8 entre les séquences de détection produites par différentes fenêtres, ou, à défaut, proximité du moment de détection dans une tolérance plus ou moins 10 pourcent.

#### 4. Formes alternatives de Sigma(t)

Objectif. Tester différentes spécifications du noeud mismatch.

Variantes testées.
- Sigma1. max(0, D(E) - Cap), spécification principale.
- Sigma2. max(0, (D(E) - Cap) / D(E)), version normalisée.
- Sigma3. ReLU(D(E) - Cap)^2, accentuation non linéaire.
- Sigma4. log(1 + max(0, D(E) - Cap)), compression.

Critère de robustesse. Maintien de la relation directionnelle Sigma vers S vers C et d'un effet d'intervention cohérent sur V.

#### 5. Bootstrap et rééchantillonnage

Objectif. Estimer l'incertitude autour du moment de détection du seuil.

Procédure.
- Générer B répliques bootstrap en blocs pour préserver l'autocorrélation.
- Recalculer la détection sur chaque réplique.
- Construire un intervalle de confiance à 95 pourcent autour du moment de détection.
- Compter la proportion de répliques où le signe de l'effet causal est reproduit.

Critère de robustesse. Intervalle de confiance inférieur à 20 pourcent de la longueur de série et taux de reproduction supérieur à 90 pourcent.

#### 6. Tests placebo

Objectif. Vérifier que la détection de seuil ne se produit pas aléatoirement.

Procédure.
- Générer des séries sans structure de seuil, bruit autocorrélé.
- Appliquer le même algorithme de détection.
- Estimer le taux de faux positifs.

Critère de robustesse. Taux de faux positifs inférieur à 5 pourcent.

#### 7. Sensibilité multidimensionnelle

Objectif. Explorer l'espace des paramètres par tirages aléatoires.

Procédure.
- Tirer N combinaisons de paramètres dans des plages fixées ex ante.
- Exécuter le pipeline pour chaque combinaison.
- Enregistrer présence de seuil, moment de seuil, signe et magnitude de l'effet causal.

Critère global. Les inférences principales, existence d'un seuil et effet causal de l'intervention, doivent rester stables dans plus de 80 pourcent de l'espace des paramètres.

#### Règle de décision pour la robustesse

Un résultat est considéré comme robuste si:
1) au moins 4 des 5 spécifications alternatives de Cap produisent un pattern de seuil comparable
2) au moins 80 pourcent des combinaisons de paramètres dynamiques reproduisent la structure causale
3) la concordance des détections sous variation de fenêtres reste supérieure à 0.7
4) l'intervalle bootstrap sur le moment de seuil reste inférieur à 15 pourcent de la longueur de la série
5) le taux de faux positifs placebo reste inférieur à 10 pourcent

Tous résultats non robustes sont rapportés en annexe avec discussion des limites.

## 9. Annexe opérationnelle
Voir `02_Protocol/ORI_C_Testable_au_Scalpel_v1_0.md` pour les définitions opératoires, les designs expérimentaux renforcés, les contrôles anti-circularité et les critères de falsification sans zone grise.

## 2.8 Règles de décision et SESOI (normatif)

Les règles de décision statistiques et l'agrégation des verdicts sont fixées ex ante dans le document `02_Protocol/DECISION_RULES_v1.md`.

Conventions non négociables :
- alpha = 0.01.
- Triplet obligatoire : p-value, IC 99 %, comparaison au SESOI.
- Verdict local par test : ACCEPT, REJECT, INDETERMINATE.
- Gate de qualité et gate de puissance avant agrégation globale.

Les résultats nuls ou négatifs sont explicitement acceptés et doivent être rapportés au même niveau que les résultats positifs.

Version : v1.0  
Date : 2026-02-17
