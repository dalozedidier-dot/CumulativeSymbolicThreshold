# Du vivant autonome au régime symbolique cumulatif
## Architecture, seuil et protocole de test

## 1. Architecture explicative minimale

### 1.1 Noyau du vivant autonome O, R, I
Un vivant autonome est défini par un cycle interne O, R, I, porté par l'auto entretien.

- Organisation O: routines, structure, spécialisation, allocation de ressources.
- Résilience R: buffers, redondances, réparation, tolérance aux chocs.
- Intégration I: arbitrages, contrôle, synchronisation, couplages internes.

### 1.2 Viabilité V(t)
V(t) est la capacité à maintenir l'auto entretien sous contrainte, mesurée sur une fenêtre [t-Δ, t].

Forme générale normalisée:
V(t) = ω1·Survie(t) + ω2·Énergie_nette(t) + ω3·Intégrité(t) + ω4·Persistance(t)

Les différences ΔV sont évaluées sur la même fenêtre [t-Δ, t], avec protocole d'intervention déclaré.

Choix opérationnels selon le domaine:
- Cellulaire: taux de croissance, intégrité membrane, charge ATP, taux d'erreurs, survie.
- Organisme: survie, coûts énergétiques, performance de tâche, blessure, reproduction.
- Groupe humain: stabilité démographique, production nette, mortalité, robustesse aux chocs, coopération.

Verrou minimal:
- Pas besoin d'un V(t) universel.
- Besoin d'un vecteur de viabilité et d'une agrégation déclarée avant test.

### 1.3 Second cycle: variation, sélection, transmission
Un second cycle externe variation, sélection, transmission rétroagit sur O, R, I et reconfigure la dynamique interne.

Condition d'activation:
- Le cycle externe est actif si le mismatch Σ(t) dépasse un seuil Σ* pendant une durée τ.

Définition:
Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t)))

- D(E): demande de l'environnement.
- C(O,R,I): capacité courante du système.
- La forme exacte de C(O,R,I) est fixée ex ante.

Exemples pour C(O,R,I), à choisir ex ante:
- Produit: C = O·R·I
- Moyenne géométrique pondérée

Critère falsifiable:
Si le second cycle s'active alors que Σ(t) ≤ Σ* presque partout, l'hypothèse d'activation sous mismatch tombe.

Conclusion:
Le symbolique devient une composante de la causalité vitale, pas un vernis culturel.

### 1.4 Intervention extérieure et conditions de possibilité
On distingue un système intrinsèquement insuffisant d'un système capable en principe mais empêché par une intervention extérieure. Cette intervention est une contrainte exogène qui modifie l'environnement effectif et les paramètres opératoires du cycle O, R, I.

Définir une variable d'intervention exogène U(t). U(t) agit par trois voies principales.

Voie A. Augmentation de la demande.
U(t) augmente la demande environnementale D(E(t)) à coûts constants. Cela élève Σ(t) et peut maintenir le système dans un régime de survie sans accumulation.

Voie B. Réduction de la capacité.
U(t) réduit la capacité C(O(t), R(t), I(t)) à demande constante. Cela élève Σ(t) et peut empêcher la stabilisation d'attracteurs cumulatifs.

Voie C. Coupure du canal symbolique.
U(t) dégrade directement la transmission en réduisant la fidélité, la densité de transmission, la codification, ou en augmentant le coût de transmission. Dans ce cas, S(t) peut exister mais C(t) plafonne.

Conséquence testable.
Si U(t) est mesurée et varie, la comparaison avec versus sans U(t) devient un test causal. Un retrait ou un affaiblissement de U(t) doit relancer C(t) et augmenter V(t) dans le régime proche ou post seuil, si l'hypothèse de cumulativité est correcte.

## 2. Variable d'ordre et basculement

### 2.1 Variable d'ordre C(t)
C(t) est une métrique opérationnelle, pas une notion vague de culture.

Définition verrou:
C(t) = gain de performance intergénérationnel dû à la transmission sociale, à génétique constante sur l'horizon T.

T est fixé ex ante.

### 2.2 Support symbolique, deux couches

Stock symbolique S(t):
S(t) = α1·Répertoire(t) + α2·Codification(t) + α3·Densité_transmission(t) + α4·Fidélité(t)

Efficacité symbolique s(t):
s(t) = ΔV(t) / ΔS(t), mesuré sous intervention sur [t-Δ, t], protocole déclaré.

S(t) décrit l'état symbolique disponible.
C(t) mesure l'effet cumulatif intergénérationnel sur la performance.
C(t) peut augmenter avec S(t), sans être identique à S(t).

Définition courte du basculement:
Régime où symboles, normes et techniques transmissibles deviennent déterminants pour la viabilité du groupe.

## 3. Démonstration mécaniste attendue

Critère central:
Montrer un seuil dynamique au delà duquel le système passe au régime symbolique cumulatif, avec signatures de transition.

Seuil principal:
ΔC(t) = C(t) - C(t-1)

Seuil franchi si:
ΔC(t) > μ_ΔC + k·σ_ΔC
pendant m pas consécutifs.

μ_ΔC et σ_ΔC sont estimés sur une période de référence pré seuil ou une condition contrôle, fixée ex ante.

Signatures attendues:
- Ralentissement critique: autocorrélation et variance augmentent avant le seuil.
- Hystérésis: retour en arrière nécessitant plus qu'une simple baisse des paramètres.
- Sensibilité accrue près du seuil.

## 4. Protocole de test

Principe:
Le symbolique doit rétroagir sur O, R, I, et les effets doivent être stabilisés, pas seulement détectables.

Critère causal:
La présence d'artefacts culturels ne suffit pas.
Le test exige que la perturbation du canal symbolique dégrade la viabilité.

L'intervention peut être:
- Expérimentale
- Simulationnelle
- Quasi expérimentale via contrefactuel instrumenté

Le protocole et l'indicateur de perturbation sont définis ex ante.
