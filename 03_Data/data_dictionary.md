# Dictionnaire de données

Ce fichier décrit les champs attendus pour les données brutes et les données traitées.

## 1. Conventions
- Tous les temps utilisent la même unité et le même pas.
- Les identifiants d'unité (agent, groupe, population) sont stables.
- Les transformations sont journalisées.

## 2. Champs minimaux recommandés

### 2.1 Index
- id: identifiant d'unité
- t: pas de temps

### 2.2 Mesures internes
- O: organisation
- R: résilience
- I: intégration

### 2.3 Viabilité
- survie
- energie_nette
- integrite
- persistance

### 2.4 Symbolique
- repertoire
- codification
- densite_transmission
- fidelite
- perturb_symbolic: 0 ou 1, indicateur simple pour démo

### 2.5 Environnement et intervention
- demande_env: proxy de D(E(t))
- U_raw: proxy optionnel d'intervention exogène

## 3. Données traitées
- V, Cap, Sigma, S, C, delta_C, threshold_hit
