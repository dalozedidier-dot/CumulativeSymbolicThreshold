# Catalogue d'interventions et contrôles

Ce fichier liste des interventions symboliques admissibles et des contrôles pour tester la causalité.

## 1. Interventions symboliques
1) Suppression d'accès au répertoire
- Cible: Répertoire(t)
- Exemple: retirer un ensemble de techniques ou de règles transmissibles
- Attendu: baisse S(t), et baisse V(t) dans le régime cumulatif

2) Dé codification
- Cible: Codification(t)
- Exemple: remplacer un code stable par une transmission ambiguë ou non standardisée
- Attendu: baisse fidélité effective, baisse C(t) et V(t) après seuil

3) Baisse de densité de transmission
- Cible: Densité de transmission(t)
- Exemple: réduire la fréquence des interactions d'apprentissage ou la connectivité
- Attendu: baisse de C(t), effet plus fort près du seuil

4) Baisse de fidélité
- Cible: Fidélité(t)
- Exemple: bruit sur la copie, erreur de transmission, dégradation des supports
- Attendu: augmentation des coûts, baisse de performance cumulée

5) Augmentation des coûts de transmission
- Cible: coût d'apprentissage, temps, énergie
- Attendu: ralentissement de l'accumulation et hausse des vulnérabilités

## 2. Contrôles négatifs
Perturbations qui ne touchent pas le canal symbolique, mais imitent une perturbation générale.
Exemples:
- fatigue générale sans modification des règles transmissibles
- variation mineure des routines sans changement de transmission

Objectif:
Vérifier la spécificité des effets symboliques.

## 3. Contrôles positifs
Interventions connues pour augmenter la transmission:
- formation structurée
- standardisation de procédures
- meilleure accessibilité des supports

Objectif:
Vérifier que S(t) peut augmenter et que C(t) suit dans les conditions attendues.

## 4. Journal d'intervention
Pour toute intervention, consigner:
- date et fenêtre [t-Δ, t]
- variable ciblée
- intensité
- mécanisme attendu
- protocole d'exécution
- résultats observés
