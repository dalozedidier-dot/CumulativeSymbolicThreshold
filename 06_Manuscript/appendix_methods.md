# Annexe A, protocole d'analyse complet

## A.1 Définitions opérationnelles

### A.1.1 Variables observables
O, R, I sont des observables ou proxys définis ex ante.

### A.1.2 Capacité Cap(t)
Cap(t) = f(O(t), R(t), I(t)). Spécification principale.
Cap(t) = 0.4·O + 0.35·R + 0.25·I.

### A.1.3 Demande D(E(t))
D(E(t)) est fixée ex ante ou estimée par proxies, selon le design.

### A.1.4 Mismatch Sigma(t)
Sigma(t) = max(0, D(E(t)) - Cap(t)).

### A.1.5 Stock symbolique S(t)
S(t) est un stock mesuré par proxies de transmission. Une forme minimale.
S(t) = a1·répertoire + a2·codification + a3·densité + a4·fidélité, poids fixés ex ante.

### A.1.6 Variable d'ordre C(t)
C(t) capture l'accumulation cumulative et suit une dynamique explicite. Exemple minimal.
C(t+1) = (1 - d)·C(t) + b·g(S(t), Sigma(t)).

V(t) n'entre pas dans la définition de C si l'on impose une non circularité stricte. Un feedback via V peut être exploré uniquement en robustesse.

### A.1.7 Viabilité V(t)
V(t) est mesurée en aval et agrégée ex ante. Exemple: moyenne pondérée de survie, énergie nette, intégrité, persistance.

## A.2 Détection de seuil

delta_C(t) = C(t) - C(t-1).  
Seuil franchi si delta_C(t) > mu + k·sigma pendant m pas consécutifs, avec mu et sigma calculés sur une fenêtre w fixée ex ante.

## A.3 Tests d'hypothèses
Gabarit à compléter selon le design choisi.

## A.4 Tests de robustesse
Voir 02_Protocol/PROTOCOL_v1.md, section robustesse.

## A.5 Logiciels
Python et dépendances listées dans environment.yml.
