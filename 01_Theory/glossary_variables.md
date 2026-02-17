# Glossaire des variables et notations

Ce fichier sert de contrat. Toute ambiguïté doit être résolue ici avant pré-enregistrement.

## Variables internes
- O(t): organisation. Routines, structure, spécialisation, allocation de ressources.
- R(t): résilience. Buffers, redondances, réparation, tolérance aux chocs.
- I(t): intégration et régulation. Arbitrages, contrôle, synchronisation, couplages internes.

## Viabilité
- V(t): score de viabilité sur une fenêtre [t-Δ, t]. Les poids ω sont fixés ex ante.
- Δ: largeur de fenêtre pour calculer V(t) et les différences ΔV.

## Environnement, capacité, mismatch
- E(t): état de l'environnement.
- D(E(t)): demande environnementale, définie par proxies.
- C(O(t), R(t), I(t)): capacité courante du système, forme fixée ex ante.
- Σ(t): mismatch, défini par Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t))).
- Σ*: seuil de stress.
- τ: durée minimale au-delà du seuil avant activation.

## Symbolique et cumulativité
- S(t): stock symbolique. Composite pondéré, poids α fixés ex ante.
- s(t): efficacité symbolique, ratio ΔV/ΔS mesuré sous intervention.
- C(t): variable d'ordre. Gain intergénérationnel dû à transmission sociale à génétique constante sur l'horizon T.
- T: horizon intergénérationnel choisi ex ante.

## Seuil de basculement
- ΔC(t): accroissement de C(t).
- μ_ΔC, σ_ΔC: moyenne et écart-type de référence, estimés ex ante.
- k: coefficient de seuil.
- m: nombre de pas consécutifs requis.

## Règles
- Paramètres décisionnels (Δ, T, τ, Σ*, k, m, ω, α) sont fixés ex ante dans la pré-inscription.
- Les variantes sont autorisées uniquement en analyses de robustesse, identifiées comme secondaires.
