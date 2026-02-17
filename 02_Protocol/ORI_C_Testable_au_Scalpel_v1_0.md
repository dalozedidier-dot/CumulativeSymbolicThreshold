# ORI-C
Testable au scalpel  
Version: 1.0  
Date: 2026-02-17

Ce document formalise des définitions opératoires, des manipulations propres, des métriques robustes, des contrôles anti-circularité et des critères de falsification sans zone grise.  
Il complète `02_Protocol/PROTOCOL_v1.md` et ne modifie pas les critères décisionnels H1 à H4.  

## 0. Définir les variables au sol
Objectif: rendre O(t), R(t), I(t) séparables, manipulables et mesurables.  
Convention: plus grand = mieux. Fixer l’orientation une fois, la conserver partout.

### 0.1 O(t). Organisation, structure
Proxies manipulables selon contexte.

- Organisation humaine: clarté des rôles, profondeur hiérarchique, taux de règles explicites, spécialisation. Shannon sur la distribution des tâches.
- Système technique: modularité, découplage, nombre de composants, profondeur de pipeline.
- Multi-agents: topologie, règles d’allocation, structuration des sous-groupes.

### 0.2 R(t). Redondance, marges
- Ressources: capacité de secours, buffers, surprovisionnement.
- Agents: agents standby, duplication de compétences.
- Information: duplication des canaux, réplication.

### 0.3 I(t). Coordination, intégration
- Synchronisation: fréquence, latence de décision.
- Cohérence: conflits de décisions, taux de rework.
- Multi-agents: taux de consensus, qualité du message passing, bruit de communication.

### 0.4 Cap(t), Σ(t), V(t). Endogènes, mesurables
Cap(t) doit être mesurée indépendamment de D(t) pour éviter la circularité.

- Cap(t). Charge maximale soutenable sans dégradation durable. Définition testable sur une fenêtre W.
  1) erreurs <= ε  
  2) latence <= Lmax  
  3) backlog non divergent  
  4) retour à l’état nominal après micro-pics

  Estimation recommandée: rampe en escalier D0, D1, D2. Tenir chaque palier W pas. Cap = dernier palier qui respecte 1 à 4.

- Σ(t). Mismatch charge vs capacité.  
  Σ(t) = max(0, D(t) - Cap(t))  
  D(t) est imposée ou mesurée via un générateur externe fixé ex ante.

- V(t). Viabilité sur fenêtre.  
  Recommandation robuste: V(t) = quantile bas q de la performance sur W, par exemple q = 0.05, plutôt qu’un minimum brut.

## 1. Noyau ORI
Chaîne causale: O, R, I -> Cap(t) -> Σ(t) -> V(t)

### 1.1 Pré-enregistrement ex ante indispensable
Avant les essais, fixer noir sur blanc:

1) la forme attendue de Cap = f(O,R,I)  
2) métriques, fenêtres, seuils, règles d’arrêt  
3) critères de falsification

### 1.2 Test T1 renforcé. O, R, I -> Cap(t)
Design recommandé: plan factoriel, randomisation, répétitions.

- Manipulation: O, R, I chacun sur 3 niveaux bas, moyen, haut. 27 conditions. Possible plan fractionnaire si nécessaire.
- Estimation Cap: rampe D(t) standardisée, paliers tenus W, contraintes 1 à 4.

Résultats attendus: effets monotones partiels et interactions plausibles.
- O augmente Cap jusqu’à un plafond si R est faible.
- R augmente Cap avec rendements décroissants.
- I augmente Cap surtout quand O et R sont non nuls.

Falsification stricte:
- non-monotonie systématique, augmenter O fait baisser Cap dans la majorité des réplicats
- absence d’effet stable, effets erratiques entre runs
- inversion robuste après contrôle des confondants

Contrôle anti-artefact: mesurer l’overhead de coordination séparément, par exemple temps de synchronisation, volume de messages, coût de routage.

### 1.3 Test T2 renforcé. Cap(t) -> Σ(t)
Éviter la tautologie pipeline.

- Cap doit être estimée dans une phase de calibration indépendante.
- D(t) doit être imposée ou mesurée via un générateur externe.

Manipulation:
- Fixer O, R, I constants.
- Utiliser Cap* de calibration.
- Monter D(t) au-delà de Cap*.

Falsification utile:
- Σ(t) reste approximativement 0 alors que D dépasse Cap* et que les métriques de stabilité se dégradent.

### 1.4 Test T3 renforcé. Σ(t) durable -> V(t) chute
Définir durable et mesurer dommage.

Manipulation:
- imposer une cible Σ(t) par exemple 10 pourcents au-dessus de Cap pendant Tdur
- comparer plusieurs durées, court, moyen, long

Mesures:
- V(t) quantile bas
- dommage: dette accumulée, backlog, erreurs cumulées, drift qualité

Hypothèse relationnelle:
- V baisse avec l’aire sous la courbe de Σ. AΣ = ∫ Σ(t) dt

Falsification:
- V stable et métriques secondaires stables malgré AΣ élevé.

## 2. Symbolique
Chaîne symbolique: S(t) -> C(t) avec ORI comparable.

Pièges à éviter:
- S comme aide ponctuelle versus S comme mémoire cumulable et transmissible
- apprentissage individuel confondu avec cumul inter-génération

### 2.1 Définir S(t) de manière manipulable
Dimensions séparables:

1) quantité: volume de documents, règles, exemples  
2) diversité: couverture de cas et variantes  
3) stabilité: persistance, versioning, faible bruit  
4) accessibilité: indexation, recherche, temps d’accès  
5) compressibilité: ratio signal sur bruit, redondance utile

Prévoir des stocks S synthétiques contrôlés, incluant une condition S riche mais toxique.

### 2.2 Définir C(t) sans confusion
C(t) est un gain inter-génération.

- une génération: nouvel agent, nouvelle équipe, ou épisode d’entraînement à partir de zéro avec accès à l’héritage
- mesure early: perf sur une phase initiale standardisée
- C(n) = Perf(n+1, early) - Perf(n, early)

## 3. Tests symboliques renforcés
### 3.1 Test T4. Effet direct S -> C à ORI comparable
Design:
- deux groupes, mêmes O, R, I, même budget temps et ressources
- A accès à S riche, B à S pauvre ou nul
- produire une génération n puis n+1

Mesures:
- C(n) sur phase early identique
- efficacité: temps pour atteindre un seuil de performance

Contrôles:
- imposer un coût d’accès à S, temps de lecture ou recherche

Falsification:
- C identique, ou gains sans généralisation.

### 3.2 Test T5. Effet différé S(t0) -> C(t0+T)
Rendre le délai crédible.

- injection S à t0
- tâches rendant S utile après diversification
- mesurer sur plusieurs générations

Attendus:
- délai avant C significatif
- corrélation avec l’usage réel de S, logs d’accès, citations, réutilisation

Falsification:
- pic ponctuel puis retour à zéro
- amélioration entièrement expliquée par O, R ou I

### 3.3 Test T6. Seuil symbolique cumulatif S*
Tester une non-linéarité.

Manipulation:
- augmenter S par paliers: 0, S1, S2, ..., Sk
- chaque palier augmente une dimension spécifique de S

Mesure:
- C à chaque palier, sur plusieurs générations

Détection:
- modèle piecewise: C approximativement 0 avant S*, C > 0 après S*
- stabilité: au-dessus de S*, C reste positif sur plusieurs cycles

Falsification:
- relation strictement linéaire sans rupture détectable
- C apparaît puis disparaît sans instabilité de protocole identifiée

### 3.4 Test T7. Coupure U(t) du symbolique, ORI constants
Manipulation:
- couper S, supprimer mémoire partagée ou rendre l’accès impossible
- garder O, R, I constants et ressources constantes

Mesures:
- C avant et après coupure, au moins 2 générations
- indicateur de réinvention: duplication du travail, entropie des solutions, divergence des procédures

Falsification:
- C inchangé et indicateurs de réinvention inchangés.

## 4. Confondants à neutraliser
1) apprentissage individuel confondu avec cumul inter-génération. imposer reset ou nouveaux agents  
2) augmentation de coordination induite par S. garder I constant ou le mesurer séparément  
3) qualité de S. inclure S riche mais toxique  
4) sélection des meilleurs agents. randomisation stricte

## 5. Minimal viable suite, courte mais robuste
Recommandation si objectif: démonstration contrôlée rapide.

- simulation multi-agents
- ORI factoriel réduit, 2 niveaux, 8 conditions
- S sur 5 paliers, coupure U au milieu
- mesures: Cap calibrée, Σ sur rampes, V quantile bas, C inter-génération early
- analyse: monotonicité ORI, relation V vs aire Σ, piecewise sur S, test de coupure
