# Du vivant autonome au régime symbolique cumulatif : architecture, seuil et protocole de test

## 1) Architecture explicative minimale

### Noyau du vivant autonome O, R, I
Un vivant autonome est défini par un cycle interne O, R, I, porté par l’auto entretien.

Organisation (O) : routines, structure, spécialisation, allocation de ressources.  
Résilience (R) : buffers, redondances, réparation, tolérance aux chocs.  
Régulation ou intégration (I) : arbitrages, contrôle, synchronisation, couplages internes.

### Viabilité V(t), métrique opérationnelle
V(t) est la capacité à maintenir l’auto entretien sous contrainte, mesurée par un score fixé a priori sur une fenêtre [t-Δ, t].

Forme générale normalisée :  
V(t) = ω₁·Survie(t) + ω₂·Énergie nette(t) + ω₃·Intégrité(t) + ω₄·Reproduction ou persistance(t)

Les différences ΔV sont évaluées sur la même fenêtre [t-Δ, t], avec protocole d’intervention déclaré.

Choix opérationnels selon le domaine :  
Cellulaire : taux de croissance, intégrité membrane, charge ATP, taux d’erreurs, survie.  
Organisme : survie, coûts énergétiques, performance de tâche, blessure, reproduction.  
Groupe humain : stabilité démographique, production nette, mortalité, robustesse aux chocs, coopération.

Verrou minimal  
Pas besoin d’un V(t) universel. Besoin d’un vecteur de viabilité et d’une agrégation déclarée avant test. La métrique est fixée ex ante.

### Second cycle, variation, sélection, transmission
Un second cycle externe variation, sélection, transmission rétroagit sur O, R, I et reconfigure sa dynamique interne.

Condition d’activation du second cycle  
Le cycle externe est actif si le mismatch Σ(t) dépasse un seuil Σ* pendant une durée τ.

Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t)))  
D(E) est la demande de l’environnement, C(O,R,I) est la capacité courante du système.

Par défaut, C(O,R,I) est une capacité synergique, par exemple C(O,R,I) = O·R·I ou une moyenne géométrique pondérée. La forme exacte est fixée avant test.

Σ* : seuil de stress.  
τ : durée minimale pour éviter les activations transitoires.

Critère falsifiable  
Si le second cycle s’active alors que Σ(t) ≤ Σ* quasi partout, l’hypothèse activation sous mismatch tombe.

Formulation verrou  
Le second cycle variation, sélection, transmission rétroagit sur O, R, I en restructurant les routines, les buffers et les arbitrages, jusqu’à ce que l’information symbolique devienne un déterminant majeur de l’auto entretien.

Formulation testable  
Cette rétroaction modifie les attracteurs du cycle O, R, I. Elle change ce qui se stabilise (O), ce qui amortit (R), et ce qui arbitre (I). Ce déplacement des régimes internes rend le basculement observable et falsifiable.

Conclusion  
Le symbolique devient une composante de la causalité vitale, pas un vernis culturel.

Option, connexion explicite à l’adaptabilité  
La variation exploratoire modulable (plasticité, apprentissage) joue le rôle de moteur de reconfiguration. La variation génétique fournit un fond de nouveauté à long terme, sans agir comme levier instantané.

## 2) Variable d’ordre et basculement

### Variable d’ordre C(t)
C(t) n’est pas la culture au sens vague. C’est une métrique opérationnelle.

Formulation verrou  
C(t) = gain de performance intergénérationnel par transmission sociale, à génétique constante sur l’horizon T considéré.

Précision sur l’horizon temporel  
T est fixé a priori de sorte que la contribution génétique soit constante ou négligeable relativement à la transmission sociale, selon un protocole déclaré.

### Support symbolique, deux couches

A. Stock symbolique S(t)  
S(t) = α₁·Répertoire(t) + α₂·Codification(t) + α₃·Densité de transmission(t) + α₄·Fidélité(t)

B. Efficacité symbolique s(t)  
s(t) = ΔV(t) / ΔS(t), mesuré sous intervention, sur la fenêtre [t-Δ, t] et avec protocole déclaré.

S(t) décrit l’état symbolique disponible.  
C(t) mesure l’effet cumulatif intergénérationnel de la transmission sur la performance.  
C(t) peut augmenter avec S(t), mais ce n’est pas une identité.

C(t) comme variable d’ordre au sens des transitions de phase  
C(t) capture le passage d’un régime où l’information transmise est marginale à un régime où elle devient structurante et stabilisatrice.

Nom du basculement  
Régime symbolique cumulatif.

Définition courte  
Un régime où symboles, normes et techniques transmissibles deviennent une part déterminante des conditions de viabilité du groupe, donc de l’auto entretien des individus.

## 3) Démonstration mécaniste attendue

Critère central  
Montrer un seuil dynamique au delà duquel le système passe au régime symbolique cumulatif, de manière robuste, non linéaire, avec signatures de transition.

Définition opérationnelle du seuil  
Critère principal, rupture de pente :  
ΔC(t) = C(t) - C(t-1)  
Seuil franchi si ΔC(t) > μ_ΔC + k·σ_ΔC pendant m pas consécutifs.

μ_ΔC et σ_ΔC sont estimées sur une période de référence pré seuil ou sur une condition contrôle, définie ex ante.

Critère de validation, signatures de transition de phase  
Ralentissement critique : autocorrélation et variance augmentent avant le seuil.  
Hystérésis : le retour en arrière exige plus qu’une simple diminution des paramètres.  
Sensibilité accrue aux perturbations près du seuil.

## 4) Protocole de test

Principe général  
Le symbolique doit rétroagir sur O, R, I, et ces effets doivent être stabilisés, pas seulement détectables.

Critère causal  
La présence d’artefacts culturels ne suffit pas. Le test exige que leur perturbation dégrade la viabilité. L’intervention peut être expérimentale, simulationnelle, ou quasi expérimentale par contrefactuel instrumenté. Le protocole et l’indicateur de perturbation sont définis ex ante.
