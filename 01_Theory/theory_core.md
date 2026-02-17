# Du vivant autonome au régime symbolique cumulatif
## Architecture, seuil et protocole de test

Voir aussi:
- option_b_non_circularity.md
- threshold_rationale.md

## 1. Architecture explicative minimale

### 1.1 Noyau du vivant autonome O, R, I
Organisation O: routines, structure, allocation de ressources.  
Résilience R: buffers, réparation, tolérance aux chocs.  
Intégration I: arbitrages, synchronisation, couplages internes.

### 1.2 Viabilité V(t)
V(t) est mesurée sur [t-Δ, t] avec une agrégation fixée ex ante.

Forme générale:
V(t) = ω1·Survie(t) + ω2·Énergie_nette(t) + ω3·Intégrité(t) + ω4·Persistance(t)

### 1.3 Mismatch et activation
Capacité:
Cap(t) = Cap(O(t), R(t), I(t)), forme fixée ex ante.

Mismatch:
Σ(t) = max(0, D(E(t)) - Cap(t))

Activation:
Le cycle externe est actif si Σ(t) > Σ* pendant au moins τ.

### 1.4 Contraintes exogènes U(t)
U(t) agit via:
- hausse de demande
- baisse de capacité
- coupure du canal symbolique

Test causal:
Comparer avec versus sans U(t), ou avant versus après variation de U(t).
