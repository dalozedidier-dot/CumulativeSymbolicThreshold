# Option B, démonstration de non circularité

Objectif:
Montrer une chaîne causale testable et non circulaire au niveau des définitions.

## Variables ex ante et observables
- D(E(t)): demande, définie ex ante via le design ou des proxys environnementaux.
- O(t), R(t), I(t): observables comportementaux ou états internes mesurés.
- U(t): contrainte exogène mesurée quand plausible.
- V(t): mesure externe de performance ou viabilité, indépendante des définitions de Cap, S, C.

## Construction, définitions
1) Capacité, dérivée uniquement de O, R, I.
Cap(t) = Cap(O(t), R(t), I(t))

2) Mismatch, dérivé uniquement de D(E) et Cap.
Σ(t) = max(0, D(E(t)) - Cap(t))

3) Stock symbolique, dérivé de proxys de transmission.
S(t) = α1·Répertoire(t) + α2·Codification(t) + α3·Densité_transmission(t) + α4·Fidélité(t)

4) Variable d'ordre, dérivée de la dynamique de transmission, pas de V.
C(t+1) = C(t) + β·g(S(t), Σ(t)) - δ·C(t)

g peut dépendre de Σ(t) si l'on modélise une pression adaptative, mais V(t) n'entre pas dans la définition de C.

5) Viabilité, issue du système et mesurée séparément.
V(t) = h(Cap(t), Σ(t), C(t), U(t)) + bruit de mesure

## Preuve de non circularité, sens strict
- Cap dépend de O, R, I uniquement.
- Σ dépend de D(E) et Cap uniquement.
- S dépend de variables symboliques observées, fixées ex ante.
- C dépend de S et éventuellement de Σ, mais pas de V.
- V dépend en aval de Cap, Σ, C et éventuellement U.

Conclusion:
Il n'y a pas de circularité de définition. Les feedbacks dynamiques restent possibles, mais ils sont explicitement modélisés, pas implicites.
