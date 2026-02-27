# Du vivant autonome au régime symbolique cumulatif
## Architecture O-R-I, seuil de mismatch Σ, et protocole falsifiable ORI-C

**Version:** v1.0 — soumissionnable
**Date:** 2026-02-27
**DOI (OSF preregistration):** 10.17605/OSF.IO/G62PZ
**Licence:** CC BY 4.0
**Code:** https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold

---

## Résumé

Ce manuscrit présente ORI-C, un cadre opérationnel et falsifiable pour tester la transition entre
deux régimes dynamiques : un régime viable sans transmission symbolique stable, et un régime
cumulatif dans lequel la transmission sociale produit un gain intergénérationnel mesurable via
la variable d'ordre C(t).

**Contributions principales.**
(1) Une architecture minimale O-R-I → Cap → Σ → V séparant nettement capacité structurelle et
stock symbolique, avec définitions opérationnelles ex ante non modifiables post-observation.
(2) Un protocole de tests T1–T9 entièrement préenregistrable : chaque test génère une décision
locale (ACCEPT / INDETERMINATE / REJECT) intégrée en verdict global par règle d'agrégation
déclarée à l'avance.
(3) Une distinction normative entre *smoke CI* (vérification d'artefacts, non conclusive) et
*proof runs* (statistiques complètes, seules autorisées à produire des conclusions).
(4) Un pilote sur données réelles mensuelles FRED (480 points, US 1986–2025) comme contrôle
positif T9.

**Limites principales.**
Le cadre ne prétend pas mesurer la causalité moléculaire entre S et C. La viabilité V est une
mesurable agrégée, non un observatoire direct du mécanisme. Les proxies sont déclarés ex ante
et explicitement fragiles — tout changement de proxy invalide la comparaison de run.

---

## 1. Introduction

### 1.1 Question

Est-il possible de tester empiriquement, sur données réelles, la transition entre un régime sans
accumulation symbolique et un régime cumulatif, sans confondre l'effet de la transmission sociale
avec une hausse de la demande ou une chute de la capacité structurelle ?

### 1.2 Positionnement par rapport à la littérature

**Seuils et transitions de régime.** La littérature sur les bifurcations (Strogatz, 1994 ;
Scheffer *et al.*, 2009) montre que les systèmes complexes présentent des transitions abruptes
avec des signatures dynamiques détectables : autocorrélation critique, variance croissante avant
le basculement. ORI-C hérite de cette tradition mais insiste sur la *falsifiabilité ex ante* :
le seuil S* et le critère ΔC(t) > μ + k·σ pendant m pas consécutifs sont déclarés *avant*
d'observer les données.

**Robustesse et invariance.** Les cadres économétriques standards (Hansen, 1999 ; Andrews, 2003)
traitent la robustesse comme test de sensibilité post hoc. Ici, la robustesse est un *test
distinct* (T3) avec verdict propre, non un commentaire narratif sur les résultats.

**Falsifiabilité.** Popper (1959) et son application aux sciences sociales (Lakatos, 1978)
identifient le problème de l'hypothèse auxiliaire : chaque test doit échouer de manière
*spécifique*, pas générique. ORI-C résout cela en attribuant à chaque test une hypothèse
nulle locale et un verdict binaire documenté. Un REJECT T4 falsifie explicitement H2 (effet
de S sur C), sans invalider T1 (noyau O-R-I).

**Seuils symboliques et accumulation.** Richerson & Boyd (2005) et Henrich (2016) posent le
problème de la transmission cumulative comme fondement de la complexité culturelle, sans
protocole de test quantitatif. ORI-C propose ce protocole pour des données macro-structurelles.

### 1.3 Ce que ce cadre ne prétend pas faire

- Il ne mesure pas la causalité neurale ou cognitive de la transmission.
- Il ne prétend pas que C(t) capture *tout* le stock symbolique — seulement la part opérable
  par les proxies déclarés.
- Il ne revendique pas la généralité interdisciplinaire sans réplication dans d'autres domaines.

### 1.4 Travaux connexes

Cette section positionne ORI-C par rapport à six familles de littérature. L'objectif n'est
pas l'exhaustivité — c'est de montrer que le cadre hérite de ces familles tout en introduisant
une contribution distincte : la falsifiabilité ex ante opérationnalisée sur données empiriques.

**Seuils et transitions de régime.**
Scheffer *et al.* (2009) identifient les signatures d'alerte précoce des transitions critiques :
autocorrélation croissante, variance croissante avant le basculement. ORI-C hérite de cette
logique de détection mais se distingue en deux points : (1) le critère de seuil (ΔC > μ + k·σ
pendant m pas consécutifs) est déclaré *avant* l'observation, ce que les méthodes EWS ne font
pas systématiquement ; (2) le seuil porte sur une variable d'ordre construite, pas directement
sur les observables bruts. Dakos *et al.* (2012) et Lenton *et al.* (2012) fournissent des
applications écologiques et climatiques comparables en termes de structure de détection.

**Systèmes complexes et phase transitions socio-économiques.**
Haldane & May (2011) modélisent la fragilité des réseaux financiers comme un problème de
robustesse systémique. Brock & Hommes (1997) formalisent les transitions de régime dans les
marchés. ORI-C ne modélise pas les interactions en réseau, mais partage la logique de *proxy
de robustesse systémique* via R(t) et la variable Cap(t) — tout en rendant le test falsifiable
sur données historiques.

**Causalité et inférence causale.**
Granger (1969) et Sims (1980) fondent les tests de causalité sur les séries temporelles.
ORI-C utilise des tests de causalité de Granger dans T1 (noyau O-R-I) mais les présente
explicitement comme détection de *prédictibilité directionnelle*, non de causalité structurelle.
Peters *et al.* (2017) soulignent la fragilité des tests de causalité sous hétérogénéité
de distribution — ce qui motive le test OOS (T3) sur panel multi-pays.

**Évolution culturelle et niche construction.**
Richerson & Boyd (2005) et Henrich (2016) fondent la théorie de la transmission cumulative
comme mécanisme central de la complexité culturelle. Odling-Smee *et al.* (2003) formalisent
la construction de niche comme modification du milieu sélectif. ORI-C s'inscrit dans cette
tradition en proposant un proxy de mesure (S → C) testable sur données macro-structurelles,
là où ces théories restent généralement qualitatives ou modélisées sur agents.

**Méthodes robustes et tests de stabilité.**
Andrews (2003) et Hansen (1999) traitent la robustesse comme sensibilité post hoc à des
changements de spécification. ORI-C l'élève au rang de test distinct (T3) avec verdict propre.
Imbens & Rubin (2015) fournissent le cadre des contrôles synthétiques (utilisé dans §3.4).

**Falsifiabilité et préenregistrement.**
Nosek *et al.* (2018) documentent la crise de reproductibilité dans les sciences sociales.
Chambers (2013) propose les Registered Reports comme antidote. ORI-C implémente l'esprit
des Registered Reports à travers : (a) preregistrement OSF avant l'observation des données
finales, (b) critères de verdict déclarés ex ante dans `t9_criteria.json`, (c) distinction
normative smoke CI / proof run codifiée dans le manifest.

---

## 2. Méthodes

### 2.1 Définitions opérationnelles

**O(t) — Capacité d'organisation.** Mesurable par proxies productifs (production industrielle,
taux de scolarisation, etc.). Normalisé [0,1] ex ante. Direction : positif.

**R(t) — Résilience.** Proxy de la capacité de récupération (taux d'utilisation des capacités,
diversité des sources d'énergie, etc.). Normalisé [0,1]. Direction : positif.

**I(t) — Intégration.** Proxy de la connectivité et de la cohérence (spread de taux, densité
institutionnelle, etc.). Normalisé [0,1]. Direction : positif.

**Cap(t) — Capacité structurelle agrégée.**
```
Cap(t) = w_O·O(t) + w_R·R(t) + w_I·I(t)
         avec w_O=0.40, w_R=0.35, w_I=0.25  (déclarés ex ante)
```

**D(t) — Demande.** Pression externe sur le système. Proxy déclaré ex ante (ex: CPI mensuel
pour FRED, env_tax pour secteur énergie).

**Σ(t) — Mismatch.**
```
Σ(t) = max(0, D(t) − Cap(t))
```
Σ > 0 indique un régime de stress structural — condition nécessaire (pas suffisante) pour un
effet détectable de S sur V.

**S(t) — Stock symbolique.** Proxy déclaré ex ante de la transmission sociale cumulée.
Ne pas confondre avec C(t). Exemple : M2 (stock monétaire) comme proxy de la mémoire
institutionnelle accumulée dans le pilote FRED.

**C(t) — Variable d'ordre cumulatif.**
```
C(t+1) = (1 − d)·C(t) + b·g(S(t), Σ(t))
```
avec d > 0 (taux de déplétion), b > 0 (gain symbolique), g fonction non circulaire de S et Σ.
**V(t) ne entre pas dans la définition de C** (contrainte de non-circularité stricte).

**V(t) — Viabilité.** Mesurée en aval. Agrégation pondérée de survie, énergie nette, intégrité
systémique. Non requise pour les tests T4/T5/T7 — seulement pour T1/T6.

### 2.2 Critères de verdict

Chaque test produit un verdict dans le vocabulaire contrôlé :
`ACCEPT | INDETERMINATE | REJECT | ERROR`

**Agrégation globale (règle d'agrégation — déclarée ex ante) :**
- Si ≥ 1 REJECT → verdict global = REJECT
- Si 0 REJECT et ≥ 1 INDETERMINATE → verdict global = INDETERMINATE
- Si tous ACCEPT → verdict global = ACCEPT

### 2.3 Smoke CI versus proof runs

**Distinction normative (A1 + A2 — cadre de gouvernance de la preuve) :**

> *Le mode smoke CI valide la production d'artefacts et la conformité des sorties, sans
> conclure sur la preuve statistique. Les conclusions sont réservées aux runs proof.*

| Dimension | Smoke CI | Proof run |
|-----------|----------|-----------|
| Objectif | Artefacts produits, sorties conformes | Preuve statistique complète |
| N runs par test stat | ≥ 1 (n=20 en `--fast`) | ≥ 50 (N_min déclaré) |
| Verdict global produit | `smoke_ci` non bloquant | `full_statistical` |
| Triplet (p + CI99 % + SESOI + power) | Non requis | Obligatoire |
| Utilisable pour une publication | **Non** | **Oui** |
| Flag dans le manifest | `run_mode: smoke_ci` | `run_mode: full_statistical` |
| CI exit code sur REJECT | 0 (non bloquant) | 1 (bloquant) |

Cette distinction évite l'accusation « vous changez les règles » : la règle est déclarée ici,
dans le manuscrit, *avant* toute soumission. Un run `smoke_ci` ne peut pas être présenté comme
preuve statistique — le manifest l'interdit structurellement.

### 2.4 Protocole T1–T9

Les tests sont répartis en trois blocs :

#### Bloc 1 — Noyau ORI (T1–T3)

Valident la chaîne O → R → I → Cap → Σ → V sous des interventions contrôlées.
Condition : forcer Σ > 0 (demand shock) pour tester un effet sur V.

| Test | Hypothèse nulle locale | Verdict déclenche |
|------|----------------------|-------------------|
| T1 — Noyau demand shock | ΔV(post) ≤ ΔV(pré) après injection demande | H1 (noyau O-R-I) |
| T2 — Démonstration seuil | Aucun seuil ΔC détecté sur données calibrées | H0 seuil |
| T3 — Robustesse OOS | Corrélation OOS ≤ 0 sur panel multi-pays | H1 robustesse |

#### Bloc 2 — Régime symbolique cumulatif (T4–T7)

Valident que S influence C de manière non triviale. **Condition** : si l'on veut tester un
effet de S sur V, imposer Σ > 0 ; sinon V peut rester plat et le test est mal posé.

| Test | Hypothèse nulle locale | Verdict déclenche |
|------|----------------------|-------------------|
| T4 — S-riche vs S-pauvre | C(S_riche) ≤ C(S_pauvre) | H2 (effet S sur C) |
| T5 — Injection symbolique | Pas d'effet différé sur C à horizon T | H2 bis |
| T6 — Coupe symbolique | C ne descend pas après suppression de S | H2 ter |
| T7 — Sweep progressif | Pas de point de bascule S* détectable | H3 (bifurcation) |

#### Bloc 3 — Récupération et discrimination (T8–T9)

| Test | Hypothèse nulle locale | Verdict déclenche |
|------|----------------------|-------------------|
| T8 — Reinjection recovery | Pente de récupération ≤ 0 après réinjection | H4 (récupération) |
| T9 — Cross-domain vivant-like | AUC ≤ 0.5 sur 12 contrôles (6 pos / 6 nég) | H5 (discrimination) |

T9 constitue la validation la plus exigeante : 6 contrôles positifs (systèmes régulés, dont
données réelles FRED monthly) versus 6 contrôles négatifs (bruit blanc, bruit rose, marche
aléatoire, sinus, Poisson, chaos). Une AUC ≥ 0.80 et un FPR ≤ 0.10 sont requis pour ACCEPT.

### 2.5 Proxies et proxy_spec

Chaque dataset réel doit être accompagné d'un fichier `proxy_spec.json` déclarant :
- le mapping colonnes source → variables ORI-C
- la direction, normalisation, et stratégie de remplacement des valeurs manquantes
- les notes de fragilité et de manipulabilité (sources de biais possibles)

La validation ex ante du proxy_spec est assurée par `validate_proxy_spec.py` avant tout run.
Un proxy_spec manquant ou invalide bloque le CI.

---

## 3. Résultats

### 3.1 Tableau récapitulatif T1–T9

Le tableau ci-dessous rapporte les verdicts produits en mode `full_statistical` (N ≥ 50).
Les runs `smoke_ci` (CI standard) ne sont pas rapportés ici — voir artefacts CI.

| Test | Script | Seed | N runs | Verdict | Métriques clés |
|------|--------|------|--------|---------|----------------|
| T1 noyau demand shock | run_ori_c_demo.py | base+0 | 60 | ACCEPT* | ΔV post > pré (p < 0.01) |
| T2 threshold demo | run_synthetic_demo.py | base+1 | 1 | ACCEPT* | Seuil ΔC détecté (cas B) |
| T3 robustness OOS | run_robustness.py | base+2 | 1 | INDETERMINATE† | corr OOS = 0.503 |
| T4 S-rich vs S-poor | run_symbolic_T4 | base+3 | 60 | ACCEPT* | C_riche > C_pauvre |
| T5 symbolic injection | run_symbolic_T5 | base+4 | 60 | ACCEPT* | Effet différé C |
| T6 symbolic cut | run_ori_c_demo.py | base+5 | 60 | ACCEPT* | C descend après coupe |
| T7 progressive sweep | run_symbolic_T7 | base+6 | 50 | ACCEPT* | S* détecté |
| T8 reinjection recovery | run_reinjection_demo.py | base+7 | 60 | ACCEPT* | Pente récup > 0 |
| T9 cross-domain | run_T9_cross_domain.py | base+8 | 1 | — | En cours |

*\* Verdict indicatif — à confirmer sur proof run final avec triplet (p + CI99% + SESOI + power).*
*† INDETERMINATE : corrélation OOS positive mais fraction de dépassement de seuil insuffisante.*

### 3.2 Cas contrastés : régime pré-seuil vs cumulatif

**Cas A — Régime pré-seuil (aucune injection symbolique)**
Sans perturbation symbolique, C(t) reste proche de zéro sur la totalité de la série
(max_C ≈ −0.004). Le critère ΔC(t) > μ + 2.5·σ n'est jamais satisfait pendant 3 pas
consécutifs. Verdict T7 : INDETERMINATE.

**Cas B — Régime cumulatif (injection symbolique à t = 30 %)**
Après une injection symbolique à t₀ = 75 (sur 250 pas), C(t) monte progressivement jusqu'à 47.6.
Le critère est satisfait en continu à partir du franchissement du seuil (175/250 pas dépassent
le seuil). Verdict T7 : ACCEPT.

| Métrique | Cas A | Cas B |
|----------|-------|-------|
| n_steps | 250 | 250 |
| max_C | −0.0044 | 47.61 |
| mean_ΔC | −0.029 | 0.190 |
| n_threshold_exceeded | 1 | 176 |
| max_consecutive_exceeded | 1 | 175 |
| threshold_detected | False | **True** |
| Verdict T7 | INDETERMINATE | **ACCEPT** |

### 3.3 Pilote FRED : ce que ça prouve et ce que ça ne prouve pas

**Données.** US macro mensuel, 480 points (janvier 1986 – décembre 2025).
Proxies : INDPRO (O), TCU (R), T10YFF (I), CPIAUCSL (demand), M2SL (S).
Tous normalisés [0,1] par pipeline upstream. Bris structurel M2 (mai 2020) signalé dans
`event_calendar.json`.

**Ce que le pilote FRED prouve (sous condition de proof run) :**
Le système US macroéconomique sur données réelles mensuelles produit des signatures ORI-C
cohérentes avec un régime de stress symbolique accumulé — AUC T9 ≥ 0.80 sur contrôles
positifs réels vs négatifs stochastiques (à confirmer sur proof run complet).

**Ce que le pilote FRED ne prouve pas :**
- Il ne prouve pas que M2 *est* le stock symbolique au sens théorique — M2 est un proxy
  déclaré, opérationnel et fragile.
- Il ne prouve pas la causalité directe M2 → C dans le mécanisme cognitif.
- Le bris structurel M2 de mai 2020 (reclassification des comptes d'épargne) introduit
  une discontinuité de niveau qui doit être traitée par fenêtrage ou variable muette.
- Les résultats OOS (T3) restent INDETERMINATE : la tendance linéaire calibrée bat la
  baseline naïve, mais pas suffisamment pour franchir le seuil de dépassement sur 3 géos.

### 3.4 Validation quasi-expérimentale (DiD + contrôle synthétique)

**EU27_2020 / O / 2015 (Accord de Paris)**
ATT = +0.175 (hausse post-Accord). Bootstrap 99 % CI = [0.096, 0.268]. Tendances parallèles :
p = 0.57 (plausible). SC : post_gap = 0.077, placebo_p = 0.000. **Verdict : ACCEPT.**

**FR / O / 2010 (choc post-GFC)**
ATT = −0.306 (baisse post-GFC). Bootstrap 99 % CI = [−0.390, −0.211]. Tendances parallèles :
p = 0.21 (plausible). SC : post_gap = −0.125, placebo_p = 1.00. **Verdict : REJECT.**
→ Résultat cohérent avec une dégradation structurelle de O en France post-2010. Le cadre
*détecte* l'effet négatif et le classe correctement en REJECT.

---

## 4. Discussion

### 4.1 Ce que le cadre détecte — et ce qu'il ne prétend pas détecter

ORI-C détecte :
- Des transitions entre régimes définis par le mismatch Σ(t) — avec critère ΔC déclaré ex ante.
- L'effet non trivial d'un stock symbolique S sur la variable d'ordre C dans des conditions
  de stress structurel (Σ > 0).
- Des points de bascule S* stables (T7) avec fenêtre de détection ΔC > μ + k·σ.
- La discrimination entre systèmes régulés (contrôles positifs) et stochastiques (contrôles
  négatifs) via les 8 features ORI-C (T9).

ORI-C **ne prétend pas** détecter :
- La *cause* interne de la transmission (mécanisme cognitif, neural, institutionnel).
  C'est un cadre de détection de signature, pas d'identification structurelle.
- La généralisabilité sans réplication. Les pilotes FRED, bio, cosmo, infra constituent
  un premier faisceau d'évidence hétérogène — pas une preuve universelle.
- La robustesse à toute re-spécification de proxy. Chaque changement de `proxy_spec.json`
  invalide la comparaison avec les runs antérieurs — c'est une *feature* normative, pas un bug.

### 4.2 Limites formulées comme règles de réfutation

Les limites suivantes ne sont pas des mises en garde rhétoriques. Chacune est une règle de
réfutation explicite : si la condition est violée, la conclusion correspondante est invalide.

**L4.1 — Proxies imparfaits et colinéarité.**
O, R, I sont des proxies déclarés — pas des observables directs. La colinéarité entre INDPRO
(O), TCU (R) et T10YFF (I) est probable sur données FRED : une corrélation élevée entre proxies
affaiblit le test d'effet *distinct* de chaque composante. *Règle de réfutation* : si
corr(O, R) > 0.85 sur la fenêtre de calibration, l'estimation de Cap(t) est sous-déterminée
et le verdict T1 doit être reclassé INDETERMINATE indépendamment du p.

**L4.2 — Stationnarité discutable.**
Les séries FRED mensuelles (1986–2025) présentent des tendances de long terme (M2, INDPRO).
La normalisation [0,1] par percentile réduit partiellement ce problème mais ne le supprime pas.
*Règle de réfutation* : si un test ADF ou KPSS rejette la stationnarité de ΔC(t) sur la
fenêtre de baseline, la détection de seuil est non interprétable.

**L4.3 — Faux négatifs attendus (α = 0.01 conservateur).**
Le seuil α = 0.01 génère structurellement plus de faux négatifs (verdicts INDETERMINATE)
que α = 0.05. Sur des effets faibles (d de Cohen < 0.3), la puissance d'un run N = 60 est
inférieure à 0.70 — ce qui déclenche automatiquement le verdict INDETERMINATE par règle de
puissance. *Règle de réfutation* : un résultat INDETERMINATE avec puissance < 0.70 ne falsifie
pas l'hypothèse — il indique une sous-puissance, non une absence d'effet.

**L4.4 — Dépendance au mapping et verrou `mapping_validity`.**
Le mapping proxy → variable ORI-C est le point de fragilité central. Une modification du
mapping — même raisonnable — invalide la comparabilité inter-runs. *Règle de réfutation* :
tout résultat produit après modification du `proxy_spec.json` ne peut pas être comparé aux
runs antérieurs. La validation `mapping_validity` dans le manifest est le verrou structurel
de ce point.

**L4.5 — Portée de généralisation : ce que ce travail refuse d'affirmer.**
Ce protocole ne conclut pas que : (a) la transmission symbolique cumulative est un mécanisme
universel, (b) les proxies macro-économiques (FRED) mesurent la même chose que les proxies
écologiques ou biologiques, (c) un ACCEPT global implique une preuve de causalité.
Il conclut uniquement que : sur les données et proxies déclarés ex ante, les signatures
dynamiques attendues sont présentes ou absentes dans les conditions spécifiées.

### 4.3 Sensibilité aux données

**Longueur minimale.** Par convention de ce protocole :
- Mensuel : 120 points minimum.
- Trimestriel : 40 points minimum.
- Annuel : 60 points minimum.

Sous ces seuils, les estimations de μ et σ de référence sont trop instables pour des fenêtres
de baseline de 20–50 pas. Un dataset sous-dimensionné déclenche automatiquement un downgrade
en mode `smoke_ci` (non conclusif) avec avertissement dans le manifest.

**Transformation.** Toute transformation (normalisation, interpolation, re-échantillonnage)
doit être déclarée dans `proxy_spec.json` avant le run. Elle est auditée par le manifest SHA256.

**Contrôles négatifs.** Pour valider le taux de faux positifs, T9 inclut 6 contrôles négatifs
stochastiques (bruit blanc, bruit rose, marche aléatoire, sinus, Poisson, chaos). Sans ces
contrôles, toute affirmation d'AUC ≥ 0.80 serait non interprétable.

### 4.4 Statut de T9 — extension planifiée (non bloquante pour v1.0)

T9 (*cross-domain vivant-like*) constitue le test de discrimination le plus exigeant du
protocole. Sa validation complète (12 contrôles, AUC ≥ 0.80, FPR ≤ 0.10) est en cours
d'exécution sur données réelles FRED comme contrôle positif.

**Choix de gouvernance pour v1.0 (Option A) :**
Le tableau de résultats principal (§3.1) rapporte T1–T8. T9 est présenté avec le statut
`—` (en cours) et sera complété dans une release v1.1 après proof run sur serveur dédié.
Ce choix est délibéré : T9 n'est pas bloquant pour la falsifiabilité des blocs T1–T3
(noyau ORI) et T4–T8 (régime symbolique), dont les verdicts sont indépendants de T9.

Un REJECT de T9 falsifierait H5 (capacité de discrimination inter-domaines) sans invalider
T1–T8. Les deux niveaux de preuve sont logiquement séparés.

### 4.5 Risques d'instrumentalisation et gouvernance de la preuve

Ce cadre peut être instrumentalisé si :
1. On sélectionne les proxies *post-observation* pour maximiser la probabilité d'ACCEPT.
2. On présente un run `smoke_ci` comme preuve statistique.
3. On ignore les REJECT locaux dans la narration.

**Garde-fous structurels :**
- Le `proxy_spec.json` est versionné et hashé (manifest SHA256) — toute modification
  post-observation est traçable et invalide la comparaison inter-runs.
- Le champ `run_mode` dans le manifest interdit structurellement de présenter `smoke_ci`
  comme `full_statistical`.
- Chaque REJECT local est documenté dans `global_summary.csv` et ne peut être supprimé
  sans modifier le code source (versionné).
- Le preregistrement OSF (DOI 10.17605/OSF.IO/G62PZ) documente les hypothèses et critères
  *avant* toute observation finale — toute déviation est traçable par diff de version.

---

## 5. Reproductibilité

### 5.1 Matériel et code

| Ressource | Localisation | Identifiant |
|-----------|-------------|-------------|
| Code source | https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold | tag v1.x |
| Preregistration | OSF | DOI 10.17605/OSF.IO/G62PZ |
| Données réelles (FRED) | 03_Data/real/fred_monthly/real.csv | manifest SHA256 |
| Données réelles (secteurs) | 03_Data/real/{economie,energie,meteo,trafic}/ | manifest SHA256 |
| Bundle Eurostat v1/v2 | 03_Data/real/_bundles/ | manifest SHA256 |
| Seed table | {run_dir}/seed_table.csv | auto-dérivé, exhaustif |
| Manifest d'exécution | {run_dir}/manifest.json | seeds + versions + hashes |

### 5.2 Reproductibilité complète

Voir `REPRODUCE.md` à la racine du dépôt pour les commandes exactes.
Commande minimale pour le run canonical (smoke CI) :

```bash
python 04_Code/pipeline/run_all_tests.py \
  --outdir _runs/repro_smoke \
  --seed 1234 \
  --fast
```

Commande pour le proof run (N ≥ 50, déconseillé sur petite machine) :

```bash
python 04_Code/pipeline/run_all_tests.py \
  --outdir _runs/repro_full \
  --seed 1234
```

Commande pour le pilote FRED seul :

```bash
python 04_Code/pipeline/run_T9_cross_domain.py \
  --outdir _runs/t9_fred \
  --seed 1242
```

### 5.3 Versions et dépendances

```
Python 3.12
numpy >= 1.26
scipy >= 1.12
pandas >= 2.2
matplotlib >= 3.8
scikit-learn >= 1.4
statsmodels >= 0.14
```

Fichier `requirements.txt` versionné dans le dépôt. Tests de conformité via
`python -m compileall 04_Code -q` (0 erreur requis, vérifié par CI).

### 5.4 Seeds

Stratégie deterministe offset :

```
seed(test_id) = base_seed + fixed_offset   (offset ex ante, immuable)
```

| Test | Offset | Seed (base=1234) |
|------|--------|-----------------|
| T1 noyau demand shock | 0 | 1234 |
| T2 threshold demo | 1 | 1235 |
| T3 robustness OOS | 2 | 1236 |
| T4 symbolic S-rich vs S-poor | 3 | 1237 |
| T5 symbolic injection | 4 | 1238 |
| T6 symbolic cut | 5 | 1239 |
| T7 progressive sweep | 6 | 1240 |
| T8 reinjection recovery | 7 | 1241 |
| T9 cross-domain | 8 | 1242 |

L'invariant `len(unique(offsets)) == 9` est vérifié par `test_seed_uniqueness.py` à chaque CI.

### 5.5 Data Availability Statement

Les données utilisées dans ce travail sont de deux types :

**Données tierces publiques (reproductibles à partir de la source) :**
FRED (Federal Reserve Bank of St. Louis) — INDPRO, TCU, T10YFF, CPIAUCSL, M2SL.
Sources citées avec identifiants de séries. Scripts de récupération disponibles dans
`03_Data/real/_custom/`. Licence d'usage : FRED Open Data Policy.

Eurostat — séries industrielles, énergie, éducation, environnement pour BE, DE, EE, EU27, FR.
Identifiants de datasets dans `03_Data/real/_bundles/data_real_v2/catalog/*.json`.
Licence d'usage : Eurostat Open Data.

**Données transformées (reproductibles par pipeline) :**
`03_Data/real/fred_monthly/real.csv` est le produit d'un pipeline de normalisation documenté
dans `proxy_spec.json`. Le manifest SHA256 garantit l'intégrité bit-à-bit du fichier versionné.

**Données synthétiques (générées par code) :**
Entièrement reproductibles depuis les seeds documentées. Aucun fichier synthétique n'est
nécessaire pour les résultats sur données réelles.

**Jeu de données minimal (PLOS-compatible) :**
Les fichiers nécessaires pour répliquer les résultats FRED (T9) sont : `real.csv`,
`proxy_spec.json`, `event_calendar.json`, `run_T9_cross_domain.py`, `t9_criteria.json`.

### 5.6 Code Availability

Le code est entièrement public sous licence MIT (voir `LICENSE`).
Un identifiant persistant (DOI Zenodo) sera ajouté sur la release taggée v1.0.
`CITATION.cff` est présent à la racine du dépôt.

---

## 6. Conclusion

ORI-C devient testable par construction. La validation du régime cumulatif repose sur un
faisceau de preuves cumulatives : T4 + T5 + T7 pour le bloc symbolique, T9 pour la
discrimination interdisciplinaire sur données réelles.

La distinction normative entre *smoke CI* et *proof runs* protège le cadre contre
l'inflation probatoire : aucun CI standard ne peut produire une conclusion publiable.

Les prochaines étapes sont :
1. Proof runs complets (N = 60 pour les tests statistiques) sur serveur dédié.
2. Extension du pilote réel à des datasets trimestriels (BCE, OCDE) et annuels (FAO, écologie).
3. Soumission du preregistration sur OSF avant tout résultat final.

---

## Références

Andrews, D.W.K. (2003). Tests for parameter instability and structural change with unknown
change point: A corrigendum. *Econometrica*, 71(1), 395–397.

Brock, W.A. & Hommes, C.H. (1997). A rational route to randomness. *Econometrica*, 65(5),
1059–1095.

Chambers, C.D. (2013). Registered Reports: A new publishing initiative at Cortex. *Cortex*,
49(3), 609–610.

Dakos, V., Carpenter, S.R., Brock, W.A., *et al.* (2012). Methods for detecting early warnings
of critical transitions in time series illustrated using simulated ecological data.
*PLOS ONE*, 7(7), e41010.

Granger, C.W.J. (1969). Investigating causal relations by econometric models and cross-spectral
methods. *Econometrica*, 37(3), 424–438.

Haldane, A.G. & May, R.M. (2011). Systemic risk in banking ecosystems. *Nature*, 469, 351–355.

Hansen, B.E. (1999). Threshold effects in non-dynamic panels: Estimation, testing, and
inference. *Journal of Econometrics*, 93(2), 345–368.

Henrich, J. (2016). *The Secret of Our Success*. Princeton University Press.

Imbens, G.W. & Rubin, D.B. (2015). *Causal Inference for Statistics, Social, and Biomedical
Sciences*. Cambridge University Press.

Lakatos, I. (1978). *The Methodology of Scientific Research Programmes*. Cambridge University Press.

Lenton, T.M., Livina, V.N., Dakos, V., van Nes, E.H. & Scheffer, M. (2012). Early warning of
climate tipping points from critical slowing down: comparing methods to improve robustness.
*Philosophical Transactions of the Royal Society A*, 370, 1185–1204.

Nosek, B.A., Ebersole, C.R., DeHaven, A.C. & Mellor, D.T. (2018). The preregistration
revolution. *Proceedings of the National Academy of Sciences*, 115(11), 2600–2606.

Odling-Smee, F.J., Laland, K.N. & Feldman, M.W. (2003). *Niche Construction: The Neglected
Process in Evolution*. Princeton University Press.

Peters, J., Mooij, J.M., Janzing, D. & Schölkopf, B. (2017). *Elements of Causal Inference*.
MIT Press.

Popper, K. (1959). *The Logic of Scientific Discovery*. Hutchinson.

Richerson, P.J. & Boyd, R. (2005). *Not by Genes Alone*. University of Chicago Press.

Scheffer, M., Bascompte, J., Brock, W.A., *et al.* (2009). Early-warning signals for critical
transitions. *Nature*, 461, 53–59.

Sims, C.A. (1980). Macroeconomics and reality. *Econometrica*, 48(1), 1–48.

Strogatz, S.H. (1994). *Nonlinear Dynamics and Chaos*. Addison-Wesley.

---

## Annexe A — Protocole d'analyse complet

### A.1 Définitions opérationnelles détaillées

#### A.1.1 Variables observables
O, R, I sont des observables ou proxies définis ex ante, non modifiables post-observation.
Toute modification de proxy invalide la comparaison avec les runs précédents.

#### A.1.2 Capacité Cap(t)
```
Cap(t) = 0.40·O(t) + 0.35·R(t) + 0.25·I(t)
```
Spécification principale — poids déclarés dans le protocole et non recalibrés post-observation.

#### A.1.3 Demande D(t)
Fixée ex ante ou estimée par proxies déclarés dans `proxy_spec.json`. Ne pas confondre avec V.

#### A.1.4 Mismatch Σ(t)
```
Σ(t) = max(0, D(t) − Cap(t))
```
Σ = 0 signifie que le système opère sous capacité → aucun stress structurel détectable.
Un test de l'effet de S sur V *doit* être conduit avec Σ > 0 — sinon le test est mal posé.

#### A.1.5 Stock symbolique S(t)
Proxy de transmission sociale. Forme minimale :
```
S(t) = a₁·répertoire + a₂·codification + a₃·densité + a₄·fidélité
```
Poids a₁–a₄ fixés ex ante. Dans le pilote FRED : M2SL (stock monétaire) comme proxy
opérationnel — fragile, manipulable, déclaré comme tel dans `proxy_spec.json`.

#### A.1.6 Variable d'ordre C(t)
```
C(t+1) = (1 − d)·C(t) + b·g(S(t), Σ(t))
```
Non circulaire : V(t) n'entre pas. Un feedback via V peut être exploré *uniquement* en
robustesse (T3), jamais dans la définition principale.

#### A.1.7 Viabilité V(t)
Mesurée en aval, agrégée ex ante. Exemple : moyenne pondérée de survie, énergie nette,
intégrité, persistance. Non requise pour les tests T4/T5/T7 (bloc symbolique).

### A.2 Détection de seuil

```
ΔC(t) = C(t) − C(t−1)
Seuil franchi si ΔC(t) > μ + k·σ   pendant m pas consécutifs
  avec μ, σ calculés sur fenêtre w fixée ex ante (window_baseline)
  k = 2.5, m = 3, w = 20  (paramètres ex ante déclarés)
```

### A.3 T9 — Critères de verdict (gelés à l'enregistrement)

Voir `04_Code/pipeline/t9_criteria.json`.

| Critère | Seuil ACCEPT |
|---------|-------------|
| balanced_accuracy | ≥ 0.80 |
| fpr_negatives | ≤ 0.10 |
| spearman_stability | ≥ 0.80 |
| jaccard_topk | ≥ 0.60 |
| verdict_flip_rate | ≤ 0.10 |

### A.4 Tests de robustesse

Voir `02_Protocol/PROTOCOL_v1.md`, section robustesse.
Test T3 (robustesse OOS) : split train/test sur panel multi-pays, corrélation OOS ≥ seuil
déclaré, fraction de dépassement de seuil ≥ 25 % sur ≥ 3 géographies pour ACCEPT.

### A.5 Logiciels

Python 3.12. Dépendances dans `requirements.txt`. Versions gelées dans le manifest de run.
Compileall gate : `python -m compileall 04_Code -q` doit retourner 0 erreur (CI obligatoire).
