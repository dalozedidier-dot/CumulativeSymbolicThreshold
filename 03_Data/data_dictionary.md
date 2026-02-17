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

### 2.2 Mesures internes (exemples)
- O_raw_*: variables brutes contribuant à O(t)
- R_raw_*: variables brutes contribuant à R(t)
- I_raw_*: variables brutes contribuant à I(t)

### 2.3 Viabilité (exemples)
- survie
- energie_nette
- integrite
- persistance

### 2.4 Symbolique (exemples)
- repertoire
- codification
- densite_transmission
- fidelite

### 2.5 Environnement
- demande_env
- choc_env

## 3. Données traitées
- O, R, I, V, Sigma, S, C, s
- Metadonnées: version protocole, paramètres, seeds, et conditions

## 4. Formats
- CSV recommandé pour tables
- JSONL recommandé pour journaux d'événements
