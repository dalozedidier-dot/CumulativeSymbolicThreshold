# Pré-enregistrement — Gabarit complet ORI-C
Version: v2
Date de scellement : ___________
Identifiant d'enregistrement : ___________
DOI de référence : 10.17605/OSF.IO/G62PZ

> **INSTRUCTION** — Ce document doit être rempli et scellé AVANT toute collecte ou analyse de données.
> Aucun paramètre ne peut être modifié après la première observation.
> Tout changement ultérieur exige un nouveau numéro de version et un nouveau dépôt.

---

## Section 1 — Question de recherche et hypothèses

### 1.1 Question principale

Existe-t-il un seuil au-delà duquel l'accumulation symbolique devient auto-renforçante (régime cumulatif) dans le système étudié ?

### 1.2 Hypothèses causales (H1–H4)

| Id | Hypothèse | Falsification immédiate |
|----|-----------|------------------------|
| H1 | **Activation** : le cycle externe s'active si Σ(t) > Σ* pendant au moins τ pas | Activation observée avec Σ(t) ≤ Σ* presque partout |
| H2 | **Basculement** : C(t) montre un changement de régime détectable et robuste | C(t) strictement nul ou strictement linéaire sur toute la série |
| H3 | **Causalité symbolique** : perturber le canal symbolique dégrade V(t) de façon réplicable dans le régime cumulatif | V(t) stable malgré coupure symbolique vérifiée |
| H4 | **Hystérésis** : le retour au régime pré-seuil exige une diminution plus forte que le franchissement | Retour symétrique observé (seuil de sortie = seuil d'entrée) |

### 1.3 Direction des effets attendus (à remplir ex ante)

| Variable | Direction attendue | Baseline de comparaison |
|----------|--------------------|------------------------|
| Cap(t) après intervention ORI | Hausse ≥ SESOI_Cap | Condition minimale sans intervention |
| V(t) après choc Σ | Baisse ≥ SESOI_V | Même série sans choc |
| C(t) après injection S | Hausse ≥ SESOI_C | Même série sans injection |
| C(t) en régime cumulatif | > 0 stable | Pré-seuil (C ≈ 0) |

---

## Section 2 — Unité d'analyse, pas de temps, horizons

| Paramètre | Valeur scellée | Justification |
|-----------|---------------|---------------|
| Unité d'analyse | ___________ | (e.g. individu, groupe, zone géographique) |
| Pas de temps δt | ___________ | (e.g. année, mois, semaine) |
| Fenêtre de viabilité Δ | ___________ | (nombre de pas pour calculer V(t)) |
| Horizon intergénérationnel T | ___________ | (nombre de pas pour C(t)) |
| Fenêtre de détection W | **20 pas** | Fixé dans PreregSpec |
| Fenêtre baseline (mu/sigma) | **30 premiers pas** | Fixé dans PreregSpec |
| Durée minimale de série | ___________ pas | Minimum pour T1–T8 |

---

## Section 3 — Définitions verrouillées des variables

> Ces définitions sont normatives. Elles ne peuvent pas être ajustées après observation.

### 3.1 Variables internes (proxies à déclarer ex ante)

| Variable | Proxy retenu | Source | Normalisation | Raison du choix |
|----------|-------------|--------|---------------|----------------|
| O(t) — Organisation | ___________ | ___________ | [0, 1] | ___________ |
| R(t) — Résilience | ___________ | ___________ | [0, 1] | ___________ |
| I(t) — Intégration | ___________ | ___________ | [0, 1] | ___________ |
| S(t) — Stock symbolique | ___________ | ___________ | [0, 1] | ___________ |

**Indépendance des proxies :** Les proxies O, R, I et S doivent être causalement indépendants (pas de proxy commun, pas de relation circulaire directe). Justifier ici : ___________

### 3.2 Capacité Cap(t)

**Forme principale (non négociable) :**
```
Cap(t) = O(t) × R(t) × I(t)
```
Forme alternative pour robustesse uniquement (secondaire, non décisionnelle) : ___________ .

**Poids ω (V(t)) :** ω₁ = 0.25, ω₂ = 0.25, ω₃ = 0.25, ω₄ = 0.25 (uniformes par défaut ; déclarer toute déviation ici : ___________ ).

**Poids α (S(t)) :** α₁ = 0.25, α₂ = 0.25, α₃ = 0.25, α₄ = 0.25 (uniformes par défaut ; déclarer toute déviation ici : ___________ ).

### 3.3 Mismatch Σ(t)

```
Σ(t) = max(0, D(E(t)) − Cap(t))
```

Proxy de demande D(E(t)) retenu : ___________ .
Source : ___________ .

### 3.4 Viabilité V(t)

```
V(t) = Σ_i ω_i · x_i(t)   sur [t−Δ, t]
```
Forme : **weighted_mean** (fixée ex ante).

### 3.5 Gain symbolique C(t) et stock S(t)

```
S(t) = Σ_j α_j · s_j(t)
C(t) = gain intergénérationnel attribuable à la transmission sociale sur T
ΔC(t) = C(t) − C(t−1)
```

Proxy de C(t) retenu (description opératoire) : ___________ .

---

## Section 4 — Contrainte exogène U(t) : définition et identification

| Aspect | Déclaration ex ante |
|--------|---------------------|
| Type de U(t) | ☐ Hausse de demande  ☐ Baisse de capacité  ☐ Coupure symbolique  ☐ Multi-stress |
| Proxy de U(t) | ___________ |
| Source de U(t) | ___________ |
| Timing t₀ (si ponctuel) | ___________ |
| Stratégie d'identification | ☐ Simulation (seed fixé)  ☐ Quasi-expérimental (discontinuité)  ☐ Instrumental  ☐ Autre : ___________ |
| Contrôle placebo prévu | ☐ Oui — description : ___________  ☐ Non — justification : ___________ |

---

## Section 5 — Critère principal de détection du seuil

```
ΔC(t) > μ_ΔC + k · σ_ΔC    pendant m pas consécutifs
```

| Paramètre | Valeur scellée | Plage de robustesse (secondaire) |
|-----------|---------------|----------------------------------|
| k (multiplicateur sigma) | **2.5** | {2.0, 3.0, 3.5} |
| m (pas consécutifs) | **3** | {2, 4} |
| Baseline (premiers n pas) | **30** | {20, 40} |

**Définitions opératoires des régimes :**

| Régime | Critère décisionnel | Ce qui compte comme preuve |
|--------|---------------------|---------------------------|
| **Pré-seuil** | C(t) ≈ 0 : \|ΔC(t)\| ≤ μ_ΔC + k·σ_ΔC sur toute la série (ou : taux de franchissement < 10 % des pas) | Aucun franchissement consécutif ; série stable |
| **Transition** | Premier franchissement détecté, mais < m pas consécutifs franchis, **ou** ΔC redevient ≤ seuil avant m | Franchissement isolé suivi de retour ; corrélation O/R/I et C partiellement relâchée |
| **Régime cumulatif** | ΔC(t) > seuil pendant **m = 3 pas consécutifs** ; C(t) > 0 stable ; amplification observable | Verdict T7 ACCEPT ; série C(t) croissante ; ATT DiD positif et CI₉₉ > 0 |
| **Non-transition (falsification)** | C(t) strictement nul ou strictement linéaire sur toute la durée post-baseline | Aucun franchissement de seuil malgré variation de S(t) ≥ SESOI_C |

---

## Section 6 — Design principal et conditions

### 6.1 Unités et conditions

| Condition | Description | N minimal |
|-----------|-------------|-----------|
| Condition contrôle | ___________ | **50** valides |
| Condition traitée | ___________ | **50** valides |

### 6.2 Assignation

Méthode : ☐ Randomisation (seed fixé : ___________ )  ☐ Quasi-expérimentale : ___________

### 6.3 Exclusion et données manquantes (voir Section 9)

---

## Section 7 — Plan d'analyse décisionnel

### 7.1 Conventions non négociables

| Convention | Valeur |
|------------|--------|
| Niveau de signification α | **0.01** |
| Intervalles de confiance | **99 %** |
| Verdict par test | **ACCEPT / REJECT / INDETERMINATE** |
| Triplet obligatoire | p-value + IC 99 % + comparaison SESOI |

### 7.2 SESOI (Smallest Effect Size of Interest) — scellés ex ante

| Variable | SESOI | Métrique |
|----------|-------|---------|
| Cap(t) | **+10 % relatif vs baseline** | ou +0.5 SD robuste (MAD) |
| V(t) — quantile bas | **−10 % relatif vs baseline** sur V_q05 | fenêtre W fixée |
| C(t) — gain symbolique | **+0.30 SD robuste (MAD)** | vs baseline pré-seuil |

### 7.3 Gates de qualité et de puissance

**Gate qualité** (évaluée avant toute décision) :
1. Taux d'échecs techniques < **5 %**
2. N valides ≥ **50** par condition
3. Aucune colonne critique manquante dans la table de runs
4. Aucun ajustement post-observation des fenêtres ou paramètres

Si la gate qualité échoue → **tous les verdicts locaux : INDETERMINATE**.

**Gate puissance** :
- Puissance cible : **80 %** au SESOI
- Si puissance estimée < **70 %** → verdict local forcé à **INDETERMINATE** (même si p ≤ 0.01)
- Méthode d'estimation : bootstrap paramétrique, B = **500** répliques

### 7.4 Tableau de décision local (par test T1–T8)

| Condition | Verdict |
|-----------|---------|
| Gate qualité échoue | INDETERMINATE |
| Puissance < 70 % | INDETERMINATE |
| p > 0.01 **ou** effet < SESOI | INDETERMINATE |
| p ≤ 0.01 **et** effet ≥ SESOI dans la bonne direction | **ACCEPT** |
| p ≤ 0.01 **et** effet ≥ SESOI dans la direction opposée | **REJECT** |

### 7.5 Tableau de décision par test (conditions spécifiques)

#### T1 — Variation O, R, I → Cap(t)
- **ACCEPT** : corrélation de Spearman (O,R,I) → Cap ≥ 0.7, p ≤ 0.01, effet monotone conforme à la forme ex ante
- **REJECT** : corrélation < 0 ou inversion de signe avec p ≤ 0.01
- **INDETERMINATE** : sinon

#### T2 — Augmentation D(E) → Σ(t)
- **ACCEPT** : Σ(t) > 0 systématiquement dès D(E) > Cap, p ≤ 0.01 pour le test de proportionnalité
- **REJECT** : Σ(t) = 0 malgré surcharge vérifiée D(E) > Cap (gate Σ=0)
- **INDETERMINATE** : sinon

#### T3 — Σ(t) élevé → V(t)
- **ACCEPT** : dégradation de V(t) significative et ≥ SESOI_V, p ≤ 0.01
- **REJECT** : V(t) stable ou croissant malgré Σ(t) durablement élevé, p ≤ 0.01
- **INDETERMINATE** : Σ(t) = 0 dans la fenêtre post (`indetermine_sigma_nul`) ; ou puissance < 70 % ; ou sinon

#### T4 — Variation S(t) → C(t)
- **ACCEPT** : effet de S(t) sur C(t) ≥ SESOI_C, p ≤ 0.01
- **REJECT** : C(t) invariant malgré ΔS(t) ≥ SESOI_C, p ≤ 0.01 pour le test de non-effet
- **INDETERMINATE** : sinon

#### T5 — Injection symbolique à t₀ → C(t+T)
- **ACCEPT** : effet différé mesurable à horizon T, p ≤ 0.01, effet ≥ SESOI_C
- **REJECT** : absence d'effet différé avec puissance ≥ 70 %
- **INDETERMINATE** : sinon

#### T6 — Coupure symbolique → C(t)
- **ACCEPT** : chute de C(t) ≥ SESOI_C, p ≤ 0.01, sans modification de O, R, I
- **REJECT** : C(t) stable malgré coupure vérifiée, p ≤ 0.01 pour le test de non-effet
- **INDETERMINATE** : sinon

#### T7 — Sweep progressif de S → C(t) (détection de seuil)
- **ACCEPT** : point de bascule stable détecté (ΔC > seuil pendant m=3 pas), non-linéarité significative
- **REJECT** : C(t) strictement linéaire sur toute la plage de S testée, p ≤ 0.01 pour test de linéarité
- **INDETERMINATE** : sinon

#### T8 — U(t) combiné, multi-stress
- **ACCEPT** : cohérence des relations causales sous stress combiné ; effets dans la direction attendue, p ≤ 0.01
- **REJECT** : relations instables ou inversées sous stress combiné, avec puissance ≥ 70 %
- **INDETERMINATE** : sinon

### 7.6 Agrégation des verdicts globaux

#### Noyau ORI (T1+T2+T3)
```
ACCEPT noyau  : T1=ACCEPT  ET  T2=ACCEPT  ET  T3=ACCEPT
               OU T1=ACCEPT ET T2=ACCEPT ET T3=INDETERMINATE (puissance insuffisante)
REJECT noyau  : au moins un parmi T1, T2, T3 = REJECT avec puissance ≥ 70 %
               ET effet dans la direction opposée
INDETERMINATE : sinon
```

#### Canal symbolique (T4+T5+T6+T7)
```
ACCEPT canal  : T4=ACCEPT  ET  au moins un de {T5, T6, T7} = ACCEPT  ET  aucun REJECT
REJECT canal  : T7=REJECT (avec puissance ≥ 70 % et T4 ≠ ACCEPT)
               OU T4=REJECT (avec puissance ≥ 70 %)
INDETERMINATE : sinon
```

#### Verdict global ORI-C
```
ACCEPT global  : ACCEPT noyau  ET  ACCEPT canal
REJECT global  : REJECT noyau  OU  REJECT canal
INDETERMINATE  : sinon
```

---

## Section 8 — Robustesse (secondaire, non décisionnelle)

> Ces analyses informent mais ne modifient PAS les verdicts principaux.

| Analyse | Paramètre varié | Plage | Critère de robustesse |
|---------|----------------|-------|----------------------|
| Cap alternatif | Forme fonctionnelle | moyenne, min, produit pondéré | Même signe directionnel dans ≥ 4/5 specs |
| Paramètres dynamiques | α_σS, β_SC, décroissances | ±50 % autour des nominaux | Structure de phases dans ≥ 80 % des combinaisons |
| Fenêtres temporelles | k ∈ {2.0, 2.5, 3.0, 3.5}, m ∈ {2, 3, 4} | Grille complète | Corrélation inter-détections ≥ 0.8 |
| Σ(t) alternative | Formes (relu, normalisée, log) | 4 variantes | Maintien de la relation directionnelle |
| Bootstrap | Répliques | B = 500 | IC sur moment de seuil < 15 % de la longueur |
| Placebo temporel | Cyclic shift N//3 | 1 variante | Pas de détection dans le placebo |
| Sous-échantillonnage | 80 % des runs | 30 répliques | Verdict stable dans ≥ 80 % des répliques |

---

## Section 9 — Exclusions et données manquantes

### 9.1 Critères d'exclusion des runs (simulation)

Un run est exclu si :
- Échec technique (exception Python non attrapée)
- Série retournée < longueur minimale déclarée en Section 2
- Colonne critique manquante (Cap, V, C, ΔC)
- Valeurs aberrantes : Cap > 1.5 ou V < −0.5 sur plus de 50 % des pas (signe de problème de simulation, non de résultat scientifique)

### 9.2 Critères d'exclusion des séries réelles

Une série réelle est exclue si :
- Taux de valeurs manquantes dans [O, R, I] > **40 %** sur la période d'analyse
- Rupture de collecte non documentée détectée par test de Chow (p ≤ 0.01)
- Proxy remplacé en cours de série sans documentation
- N < 15 observations après nettoyage

### 9.3 Imputation

Méthode d'imputation déclarée ex ante : ___________
(Par défaut : **aucune imputation** — exclusion des points manquants des calculs de corrélation et de régression ; Cap n'est pas imputé.)

Valeur maximale imputable sans exclusion : ___________ % de la série.

---

## Section 10 — Sorties prévues

### 10.1 Fichiers obligatoires par run

```
<outdir>/
├── tables/
│   ├── summary.csv       # ligne unique avec colonne 'verdict'
│   └── summary.json      # équivalent JSON
├── verdict.txt           # token unique : ACCEPT | REJECT | INDETERMINATE
├── params.txt            # seed + tous les paramètres fixes du run
└── figures/              # PNG (recommandé)
```

### 10.2 Fichiers de la suite canonique (T1–T8)

```
05_Results/canonical_tests/
├── global_summary.csv
├── verdicts_local.csv
├── verdicts_global.json
└── diagnostics.md
```

### 10.3 Figures minimales requises pour publication

1. Série temporelle de C(t) et ΔC(t) pour le cas de base (régime cumulatif confirmé)
2. Même figure pour un cas pré-seuil (contraste)
3. Courbe de sweep T7 : C(t) vs S progressif avec point de bascule annoté
4. Table de verdicts T1–T8 avec gates de qualité et puissance

### 10.4 Registre de modifications

Tout changement post-scellement doit être consigné ici :

| Date | Paramètre modifié | Ancienne valeur | Nouvelle valeur | Justification | Nouveau n° de version |
|------|------------------|----------------|----------------|--------------|----------------------|
| — | — | — | — | — | — |

---

*Document scellé le : ___________
Signataire(s) : ___________
Hash SHA-256 de ce fichier au moment du scellement : ___________*
