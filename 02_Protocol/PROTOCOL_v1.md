# PROTOCOL v1

Version: v1  
Date: 2026-02-17

## 1. Objet et question
Tester un basculement vers un régime symbolique cumulatif.

## 2. Hypothèses et falsification
H1 Activation:
Le cycle externe s'active si Σ(t) > Σ* pendant au moins τ.

Falsification H1:
Activation observée alors que Σ(t) ≤ Σ* presque partout.

H2 Basculement:
C(t) montre un changement de régime au franchissement d'un seuil.

H3 Causalité:
Perturber le canal symbolique dégrade V(t) de façon réplicable dans le régime cumulatif.

H4 Hystérésis:
Le retour au régime pré seuil exige une diminution plus forte des paramètres que celle du franchissement.

## 3. Unités, temps, fenêtres
Déclarer unité, pas de temps, Δ, T, τ ex ante.

## 4. Variables
Voir 01_Theory/glossary_variables.md.

## 5. Critère principal de seuil
ΔC(t) = C(t) - C(t-1)

Seuil franchi si:
ΔC(t) > μ_ΔC + k·σ_ΔC
pendant m pas consécutifs.

## 6. Signatures attendues
Ralentissement critique, hystérésis, sensibilité accrue.

## 7. Contraintes exogènes U(t)
Si une intervention extérieure est plausible, définir U(t) et la mesurer.

Trois voies:
1) Hausse de demande: U(t) augmente D(E(t)), Σ(t) augmente.
2) Baisse de capacité: U(t) réduit C(O,R,I), Σ(t) augmente.
3) Coupure du canal symbolique: U(t) dégrade la transmission, C(t) plafonne.

Test causal:
Comparer avec versus sans U(t), ou avant versus après variation de U(t), sur V(t), C(t), et signatures.

## 8. Designs acceptés
Simulation, expérimental, quasi expérimental, séries historiques instrumentées.

## 9. Interventions et contrôles
Voir INTERVENTIONS_CATALOG.md.

## 10. Plan d'analyse enregistré
Prétraitement, calculs, seuil, signatures, causalité, robustesse, rapport.

## 11. Risques de circularité
C(t) ne doit pas être construit tautologiquement à partir des mêmes composantes que V(t).

## 12. Reproductibilité
Seeds, versions, journal de run, données synthétiques minimales.
