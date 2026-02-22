# Changelog

## v1.2 (2026-02-22) — Correctifs audit structurel

### 6.1 — Seeds : correction de l'assertion "independent seeds" (faux)

**Constat d'audit** : la déclaration "independent seeds" était factuellement fausse.
Tous les seeds sont des offsets déterministes du seed de base (`--seed`, défaut 1234) :

| Test | Seed (base=1234) | Formule |
|------|-----------------|---------|
| T1   | 1234            | base+0  |
| T2   | 1234            | base+0  |
| T3   | 1234            | base+0  |
| T4   | 1234            | base+0  |
| T5   | 1251            | base+17 |
| T6   | 1237            | base+3  |
| T7   | 1333            | base+99 |
| T8   | 1239            | base+5  |

Les seeds T1–T4 partagent la valeur 1234 : **il n'y a pas d'indépendance inter-tests
au sens strict**.

**Correctif** (`run_all_tests.py`) :
- Docstring réécrit : "seeds are deterministic offsets of base_seed, NOT independent between tests"
- `seed_table.csv` auto-dérivé au moment du run (exhaustif, non déclaré manuellement)
- `manifest.json` contient `seed_strategy`, `seed_table[]` (test_id, seed, seed_formula, n_runs)
- Les anciens manifests sans ces champs sont des versions antérieures non conformes

### 6.2 — Run_mode : déclassement "full support" → "smoke_ci"

**Constat d'audit** : T1 et T6 utilisent `--n-runs 1` (run unique déterministe).
La sortie CI ne contient ni CI 99%, ni SESOI, ni power gate → ne satisfait pas
le triplet décisionnel des DECISION_RULES v1/v2. Employer "full empirical support"
ou "full support" pour ces runs est une sur-assertion de portée.

**Correctif** (`run_all_tests.py`) :
- `manifest.json` contient `"run_mode": "smoke_ci"` dès qu'un test a n_runs=1
- `"run_mode_note"` précise : "smoke_ci: pipeline execution check only. Does NOT satisfy
  DECISION_RULES v1/v2 full statistical requirements."
- `global_summary.csv` contient la colonne `n_runs` par test

**Règle d'interprétation** : un run smoke_ci donne une confirmation d'exécution correcte
du pipeline, pas une validation statistique au standard du protocole pré-enregistré.

### 6.3 — Rapports externes v2.1 / v2.2 : statut obsolète/non-conforme

Les rapports PDF v2.1 et v2.2 (externes au dépôt) contiennent :
- **v2.1** ("Real-Data Validation on FRED") : seuil alpha = 0.00125 (Bonferroni),
  T8 FAIL à p=0.073 qualifié de "marginal" et résumé "Strong support" — incohérence
  interne (seuil annoncé ↔ qualificatif ↔ verdict FAIL).
  **Statut : superseded — erratum déclaré ici. Ne pas citer sans note de correction.**
- **v2.2** ("Canonical Tests Suite") : déclaration "independent seeds" fausse,
  ligne "Seeds: 1234/1237/1239/1333" incomplète (manque 1251 pour T5).
  **Statut : non-conforme sur exactitude factuelle seeds. Remplacé par v1.2+ du pipeline.**

Tout rapport futur doit :
1. Dériver les seeds du `seed_table.csv` auto-généré (pas de déclaration manuelle)
2. Indiquer `run_mode` (smoke_ci ou full_statistical) dans le titre ou sous-titre
3. Ne pas employer "full support / full empirical support" pour un run smoke_ci

### 6.4 — Séparation vocabulaire : synthétique vs données réelles (rappel)

Déjà implémenté en v1.1. Rappel des invariants :
- Suite synthétique : `run_all_tests.py` → T1-T8 avec interventions simulées
- Suite données réelles : `run_real_data_canonical_suite.py` → T1-T8 avec tests causaux
- Ces deux T1-T8 ne sont **pas isomorphes** et ne doivent pas apparaître dans le même
  tableau comme s'il s'agissait des mêmes tests

---

## v1.1 (2026-02-21)

### T8 — Amendement de protocole : changement de définition

**T8 a été redéfini.** Ce n'est PAS un revirement statistique sur le même test :
c'est un changement de la question posée. Toute comparaison de verdict T8
entre un rapport antérieur à v1.1 et un rapport v1.1+ compare des tests différents.

| Version    | Nom court              | Opération testée                                          | Script / logique                        |
|------------|------------------------|-----------------------------------------------------------|-----------------------------------------|
| ≤ v1.0     | Dose-response S→C      | Réponse quantitative de C à différentes doses de S        | retiré (résultats non comparables)      |
| v1.1 synth | Reinjection recovery   | Coupure symbolique puis réinjection → récupération de C   | `run_reinjection_demo.py`               |
| v1.1 réel  | Stabilité C post-seuil | C_positive_frac_post > 0.5 ET C_mean_post > C_mean_pre   | `run_real_data_canonical_suite.py` T8   |

**Règle d'interprétation** : un changement de verdict T8 entre deux rapports de
versions différentes reflète le changement de définition, non une instabilité
statistique. Ne pas interpréter comme un revirement.

**Statut pré-enregistrement** : les DECISION_RULES v1 et v2 définissent T1–T7
uniquement. T8 a été ajouté hors périmètre pré-enregistré initial. Il est
considéré comme test confirmatoire secondaire jusqu'à un nouveau pré-enregistrement
formel. Il n'entre pas dans les règles d'agrégation ACCEPT/REJECT des
DECISION_RULES v1/v2 (agrégation limitée à T1–T3 noyau et T4–T7 symbolique).

### Séparation rapport synthétique / données réelles
- `scripts/generate_fred_report_pdf.py` refactorisé : lit désormais
  `run_real_data_canonical_suite.py` output (`global_summary.json`) en priorité,
  avec fallback sur `verdict.json` legacy.
- Run canonique FRED lancé : `05_Results/fred_monthly_canonical/` — ACCEPT global
  (6/8 : T5 INDETERMINATE, T6 INDETERMINATE attendu).
- Les T1–T8 du rapport données réelles sont explicitement distincts des T1–T8
  de la suite synthétique (`run_all_tests.py`).

---

## v1 (2026-02-17)
- Cadre public initial.
- U(t) intégré dans théorie, glossaire, protocole et pré-enregistrement.
- Démo end to end sur données synthétiques.
- Ajout d'une démo ORI-C exécutable (Option B) avec tests causaux synthétiques.
- Badge DOI et lien OSF.
