# Catalogue d'interventions et contrôles

Ce fichier liste des interventions symboliques admissibles et des contrôles pour tester la causalité.

## 1. Interventions symboliques

1) Suppression d'accès au répertoire
- Cible: Répertoire(t)
- Exemple: retirer un ensemble de techniques ou de règles transmissibles
- Attendu: baisse de S(t), et baisse de V(t) dans le régime cumulatif

2) Dé codification
- Cible: Codification(t)
- Exemple: remplacer un code stable par une transmission ambiguë ou non standardisée
- Attendu: baisse de fidélité effective, baisse de C(t) et de V(t) après seuil

3) Baisse de densité de transmission
- Cible: Densité_transmission(t)
- Exemple: réduire la fréquence des interactions d'apprentissage ou la connectivité
- Attendu: baisse de C(t), effet plus fort près du seuil

4) Baisse de fidélité
- Cible: Fidélité(t)
- Exemple: bruit sur la copie, erreur de transmission, dégradation des supports
- Attendu: augmentation des coûts, baisse de performance cumulée

5) Augmentation des coûts de transmission
- Cible: coût d'apprentissage, temps, énergie
- Attendu: ralentissement de l'accumulation et hausse des vulnérabilités

## 2. Contraintes exogènes U(t)
U(t) décrit une contrainte extérieure. Trois familles.

A. Hausse de demande
- U(t) augmente D(E(t)).
- Effet attendu: Σ(t) augmente, maintien en régime de survie.

B. Baisse de capacité
- U(t) réduit C(O(t), R(t), I(t)).
- Effet attendu: Σ(t) augmente, empêchement d'attracteurs cumulatifs.

C. Coupure du canal symbolique
- U(t) dégrade la transmission, par exemple baisse de fidélité, baisse de densité, baisse de codification, hausse de coûts.
- Effet attendu: S(t) peut exister, C(t) plafonne.

## 3. Contrôles négatifs
Perturbations qui ne touchent pas le canal symbolique, mais imitent une perturbation générale.

Exemples:
- fatigue générale sans modification des règles transmissibles
- variation mineure des routines sans changement de transmission

Objectif:
Vérifier la spécificité des effets symboliques.

## 4. Contrôles positifs
Interventions connues pour augmenter la transmission:
- formation structurée
- standardisation de procédures
- meilleure accessibilité des supports

Objectif:
Vérifier que S(t) peut augmenter et que C(t) suit dans les conditions attendues.

## 5. Journal d'intervention
Pour toute intervention, consigner:
- date et fenêtre [t-Δ, t]
- variable ciblée
- intensité
- mécanisme attendu
- protocole d'exécution
- résultats observés
