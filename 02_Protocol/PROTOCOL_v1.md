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
