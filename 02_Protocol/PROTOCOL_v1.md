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

## 8. Robustesse (secondaire, non décisionnelle)

Objectif: tester la sensibilité des résultats principaux à des variations raisonnables de paramètres de mesure. Ces analyses ne modifient pas les critères décisionnels H1 à H4.

Variantes fixées ex ante:
1) Poids ω pour V(t). Variation de plus ou moins 20% autour des valeurs principales, avec renormalisation pour conserver une somme égale à 1.
2) Poids α pour S(t). Variation de plus ou moins 20% autour des valeurs principales, avec renormalisation pour conserver une somme égale à 1.
3) Fenêtre Δ de lissage descriptif. Valeurs candidates: Δ ∈ {1, 3, 5, 7}. Ici Δ=1 correspond à aucun lissage. Le lissage sert uniquement à évaluer la stabilité, il ne redéfinit pas les variables décisionnelles.

Application:
- Recalculer V(t), S(t), Cap(t), Σ(t), C(t) et la détection de seuil sous chaque variante.
- Reporter les changements éventuels sur: détection de seuil, position du seuil, et effet de perturbation symbolique sur V(t).

Critère de stabilité:
- Si au moins 80% des variantes aboutissent à la même conclusion binaire que l'analyse principale, la stabilité est considérée comme satisfaisante.
- Sinon, la sensibilité est signalée comme limitation.

Implémentation:
- Script dédié: 04_Code/pipeline/run_robustness.py
- Sortie attendue: 05_Results/tables/robustness_results.csv
