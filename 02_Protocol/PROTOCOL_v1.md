# PROTOCOL v1

Version: v1  
Date: 2026-02-17

## 1. Objet et question
Ce protocole teste l'hypothèse d'un basculement vers un régime symbolique cumulatif, défini comme un régime où symboles, normes et techniques transmissibles deviennent déterminants pour la viabilité du groupe.

## 2. Hypothèses et falsification
H1 Activation:
Le cycle externe variation, sélection, transmission s'active si Σ(t) > Σ* pendant au moins τ.

Falsification H1:
Si une activation est observée alors que Σ(t) ≤ Σ* presque partout, l'hypothèse tombe.

H2 Basculement:
C(t) présente un changement de régime au franchissement d'un seuil, avec rupture de pente et signatures de transition.

Falsification H2:
Si aucun changement de régime robuste n'est observé sous variation contrôlée des paramètres, l'hypothèse tombe.

H3 Causalité:
La perturbation du canal symbolique dégrade V(t) de manière significative dans le régime cumulatif, et nettement moins avant seuil.

Falsification H3:
Si la perturbation symbolique ne modifie pas V(t) de façon réplicable, l'hypothèse tombe.

H4 Hystérésis:
Le retour au régime pré seuil exige une diminution plus forte des paramètres que celle qui a déclenché le franchissement.

## 3. Unités, temps, fenêtres
- Unité d'analyse: à déclarer (cellule, organisme, groupe humain, agent en simulation).
- Pas de temps: à déclarer.
- Fenêtre de viabilité: [t-Δ, t], avec Δ fixé ex ante.
- Horizon intergénérationnel pour C(t): T fixé ex ante.

## 4. Variables et définitions opérationnelles
Les définitions détaillées sont dans 01_Theory/glossary_variables.md.

## 5. Critère principal de seuil
Définir ΔC(t) = C(t) - C(t-1).

Seuil franchi si:
ΔC(t) > μ_ΔC + k·σ_ΔC
pendant m pas consécutifs.

μ_ΔC et σ_ΔC sont estimés sur une période de référence pré seuil ou une condition contrôle, fixée ex ante.
k et m sont fixés ex ante.

## 6. Signatures de transition attendues
- Ralentissement critique: autocorrélation et variance augmentent avant le seuil.
- Hystérésis: inversion nécessitant un changement plus fort des paramètres que celui du franchissement.
- Sensibilité accrue: amplitude de réponse aux perturbations maximisée près du seuil.

## 7. Contraintes exogènes U(t), contrôle des confusions
Si une intervention extérieure est plausible, définir U(t) et la mesurer. U(t) doit être intégrée au design, soit comme condition expérimentale, soit comme covariable, soit via un instrument contrefactuel déclaré.

Trois voies à distinguer:
- Hausse de demande: U(t) augmente D(E(t)), ce qui élève Σ(t) et peut maintenir un régime de survie sans accumulation.
- Baisse de capacité: U(t) réduit C(O,R,I), ce qui élève Σ(t) et empêche la stabilisation d'attracteurs cumulatifs.
- Coupure du canal symbolique: U(t) dégrade la transmission, ce qui peut faire plafonner C(t) même si un stock S(t) existe.

Critère causal recommandé:
Comparer des conditions avec versus sans U(t), ou avant versus après variation de U(t), et tester l'impact sur V(t), C(t), et les signatures de transition. La coupure du canal symbolique par U(t) est traitée comme une perturbation causale du canal de transmission.

## 8. Designs acceptés
Déclarer un design principal et, si besoin, des designs secondaires.

Design A Simulation mécaniste:
- Modèle agents ou équations avec O, R, I.
- Environnement avec demande D(E(t)).
- Canal symbolique paramétré (fidelité, densité, coût, vitesse).
- Interventions directes: couper transmission, bruiter codification, augmenter coût.

Design B Expérimental ou quasi expérimental:
- Mesures longitudinales de S, C, V.
- Intervention instrumentée sur le canal symbolique.
- Contrefactuel: différence de différences, matching, instrument, ou discontinuité.

Design C Séries historiques instrumentées:
- Proxies S, C, V sur séries temporelles.
- Détection de change point pré enregistrée.
- Validation contrefactuelle quand possible.

## 9. Interventions et contrôles
Voir 02_Protocol/INTERVENTIONS_CATALOG.md.

## 10. Plan d'analyse enregistré
1) Prétraitement: normalisation, lissage éventuel, gestion des valeurs manquantes, fixés ex ante.  
2) Calcul des variables: O, R, I, V, Σ, S, C, s, et U(t) si applicable.  
3) Seuil: application du critère décisionnel.  
4) Signatures: autocorrélation, variance, sensibilité, hystérésis.  
5) Causalité: effets sur V(t) lors de perturbations symboliques et effets de U(t) si applicable.  
6) Robustesse: variantes déclarées, non décisionnelles.  
7) Rapport: publication des résultats, y compris négatifs.

## 11. Risques de circularité
C(t) ne doit pas être construit tautologiquement à partir des mêmes composantes que V(t).
Déclarer explicitement les chevauchements et justifier la séparation.

## 12. Reproductibilité
- Seeds fixés.
- Versions des dépendances.
- Journal de run.
- Données synthétiques minimales pour reproduire la chaîne d'analyse.
