# PROTOCOL v1
Version: v1
Date: 2026-02-17

## 1. Objet et question
Ce protocole teste l'hypothèse d'un basculement vers un régime symbolique cumulatif, défini comme un régime où symboles, normes et techniques transmissibles deviennent une part déterminante des conditions de viabilité du groupe, donc de l'auto entretien des individus.

## 2. Hypothèses et falsification
H1 Activation:
Le cycle externe variation, sélection, transmission s'active si Σ(t) > Σ* pendant au moins τ.

Falsification H1:
Si une activation est observée alors que Σ(t) ≤ Σ* quasi partout, l'hypothèse tombe.

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

### 4.1 Viabilité
V(t) est un score normalisé fixé ex ante sur [t-Δ, t].
La formule et les poids ω sont fixés ex ante.

### 4.2 Mismatch
Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t))).
La forme de C(O,R,I) est fixée ex ante.

### 4.3 Stock symbolique et efficacité
S(t) est un composite de Répertoire, Codification, Densité de transmission, Fidélité, avec poids α fixés ex ante.
s(t) = ΔV(t) / ΔS(t), mesuré sous intervention.

### 4.4 Variable d'ordre
C(t) mesure le gain de performance intergénérationnel par transmission sociale, à génétique constante sur l'horizon T, défini ex ante.

## 5. Critère principal de seuil
Définir ΔC(t) = C(t) - C(t-1).
Seuil franchi si ΔC(t) > μ_ΔC + k·σ_ΔC pendant m pas consécutifs.
μ_ΔC et σ_ΔC sont estimés sur une période de référence pré seuil ou sur une condition contrôle, définie ex ante.
k et m sont fixés ex ante.

## 6. Signatures de transition attendues
- Ralentissement critique: augmentation de l'autocorrélation et de la variance avant le seuil.
- Hystérésis: inversion nécessitant un changement plus fort des paramètres que celui du franchissement.
- Sensibilité accrue: amplitude de réponse aux perturbations maximisée près du seuil.

## 7. Designs acceptés
Déclarer un design principal et les designs secondaires éventuels.

### Design A Simulation mécaniste
- Modèle agents ou équations avec O, R, I.
- Environnement avec demande D(E(t)).
- Canal symbolique paramétré (fidelité, densité, coût, vitesse).
- Interventions directes: couper transmission, bruiter codification, augmenter coût.

### Design B Expérimental ou quasi expérimental
- Mesures longitudinales de S, C, V.
- Intervention instrumentée sur le canal symbolique.
- Contrefactuel: différence de différences, matching, instrument, ou discontinuité.

### Design C Séries historiques instrumentées
- Proxies S, C, V sur séries temporelles.
- Détection de change point pré enregistrée.
- Validation contrefactuelle quand possible.

## 8. Interventions et contrôles
Les interventions détaillées sont dans 02_Protocol/INTERVENTIONS_CATALOG.md.

## 9. Plan d'analyse enregistré
1) Prétraitement: règles de normalisation, lissage éventuel, et gestion des valeurs manquantes, fixées ex ante.
2) Calcul des variables: O, R, I, V, Σ, S, C, s.
3) Seuil: application du critère décisionnel.
4) Signatures: autocorrélation, variance, sensibilité, hystérésis.
5) Causalité: effets sur V(t) lors de perturbations symboliques.
6) Robustesse: variantes déclarées, non décisionnelles.
7) Rapport: publication des résultats, y compris négatifs.

## 10. Risques de circularité
C(t) ne doit pas être construit de manière tautologique à partir des mêmes composantes que V(t).
Déclarer explicitement les chevauchements éventuels et justifier la séparation.

## 11. Reproductibilité
- Seeds fixés.
- Versions des dépendances verrouillées.
- Journal de run.
- Données synthétiques minimales fournies pour reproduire la chaîne d'analyse.
