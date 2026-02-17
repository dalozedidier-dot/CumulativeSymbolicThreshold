# Du vivant autonome au régime symbolique cumulatif
## Architecture, seuil et protocole de test

## 1. Architecture explicative minimale

### 1.1 Noyau du vivant autonome O, R, I
Un vivant autonome est défini par un cycle interne O, R, I, porté par l'auto entretien.

Organisation O: routines, structure, spécialisation, allocation de ressources.  
Résilience R: buffers, redondances, réparation, tolérance aux chocs.  
Intégration I: arbitrages, contrôle, synchronisation, couplages internes.

### 1.2 Viabilité V(t)
V(t) est la capacité à maintenir l'auto entretien sous contrainte, mesurée sur une fenêtre [t-Δ, t].

Forme générale normalisée:
V(t) = ω1·Survie(t) + ω2·Énergie_nette(t) + ω3·Intégrité(t) + ω4·Persistance(t)

Les différences ΔV sont évaluées sur la même fenêtre [t-Δ, t], avec protocole d'intervention déclaré.

Verrou minimal:
Pas besoin d'un V(t) universel. Besoin d'un vecteur de viabilité et d'une agrégation déclarée avant test.

### 1.3 Second cycle: variation, sélection, transmission
Condition d'activation:
Le cycle externe est actif si le mismatch Σ(t) dépasse un seuil Σ* pendant une durée τ.

Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t)))

D(E): demande de l'environnement.  
C(O,R,I): capacité courante du système, forme fixée ex ante.

Critère falsifiable:
Si le cycle s'active alors que Σ(t) ≤ Σ* presque partout, l'hypothèse tombe.

Conclusion:
Le symbolique devient une composante de la causalité vitale, pas un vernis culturel.

### 1.4 Contraintes exogènes U(t)
On distingue un système intrinsèquement insuffisant d'un système capable en principe mais empêché par une contrainte exogène.

Définir U(t). Trois voies principales.

Voie A. Hausse de demande.
U(t) augmente D(E(t)), ce qui élève Σ(t) et peut maintenir un régime de survie sans accumulation.

Voie B. Baisse de capacité.
U(t) réduit C(O,R,I), ce qui élève Σ(t) et empêche la stabilisation d'attracteurs cumulatifs.

Voie C. Coupure du canal symbolique.
U(t) dégrade la transmission, ce qui peut faire plafonner C(t) même si S(t) existe.

Conséquence testable:
Si U(t) est mesurée et varie, la comparaison avec versus sans U(t) devient un test causal.
