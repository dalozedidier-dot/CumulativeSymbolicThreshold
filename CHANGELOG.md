# Changelog

## v1.3 (2026-02-22) — Verrou machine "full support" + conformance suite données réelles

### A — Verrou "full_statistical_support" : Option B machine-enforced

**Constat d'audit** : la correction de vocabulaire en v1.2 était un garde-fou éditorial
(règle dans la docstring). Tant que `run_mode=smoke_ci`, rien ne bloquait mécaniquement
l'émission de "full support" en rapport. Un verrou calculé manquait.

**Choix retenu : Option B** (gate machine, pas seulement convention).

**Implémentation** (`analyse_verdicts_canonical.py` — réécrit) :

Nouveau `_run_full_validation_gate()` : pour chaque test statistique (T1, T4–T8),
lit `tables/verdict.json` ou `summary.json` et vérifie :
1. Les 4 booléens du triplet **présents ET True** : `p_ok`, `ci_ok`, `sesoi_ok`, `power_ok`
2. **N ≥ 50** par condition (champ : `n_runs_total` pour T1/T6, `n_runs` pour T8, `n` pour T4/T5 ; T7 exempt car B=500 >> 50)

`_support_level(global_v, run_mode, gate_passed)` — nouveau troisième argument :

| `run_mode` | `gate_passed` | `global` | → `support_level` |
|-----------|--------------|---------|-------------------|
| `full_statistical` | True | ACCEPT | `full_statistical_support` |
| `full_statistical` | False | ACCEPT | `full_statistical_gates_failed` |
| `smoke_ci` | (any) | ACCEPT | `smoke_ci_accept` |
| (any) | (any) | REJECT | `rejected` |
| (any) | (any) | INDETERMINATE | `inconclusive` |

`global_verdict.json` contient désormais :
- `full_validation_gate` : résultat détaillé par test (passed, reason si échec)
- `forbidden_report_labels` : liste des labels interdits pour ce run spécifique
  (ex. `["full support", "full empirical support", "full_statistical_support"]` pour smoke_ci)

**Tests T2/T3** : exemptés du gate (test_type=fixed_data, n=1 par construction protocolaire).
**Test T7** : exempt du check N (B=500 bootstrap >> N_MIN par construction).

### B — Conformance suite données réelles

**Constat** : `run_real_data_canonical_suite.py` utilisait une règle de verdict global
non-protocolaire (≥6/8 ACCEPT → ACCEPT) divergeant de `analyse_verdicts_canonical.py`.

**Correctif** (`run_real_data_canonical_suite.py`) :
- Arbre décisionnel aligné : `_aggregate_core()` + `_aggregate_symbolic()` + `_aggregate_global()`
  identiques à `analyse_verdicts_canonical.py` (DO NOT DIVERGE)
- `_support_level_real()` : vocabulaire contrôlé pour la suite réelle
  - `"real_data_canonical_support"` sur ACCEPT (jamais `"full_statistical_support"`)
  - `"rejected"` / `"inconclusive"` sinon
- `global_summary.json` contient `run_mode="real_data_canonical"`, `core_verdict`,
  `symbolic_verdict`, `support_level`, `support_level_note`

**Commentaire de pre-observation supprimé** de `real_data_canonical_T1_T8.yml`
(commentaire hardcodant "GLOBAL VERDICT: ACCEPT (7/8 ...)" incompatible avec
la discipline de pré-enregistrement).

### C — Clarification vocabulaire statistique vs synthétique

**Question** : "statistical c'est pas synthétique ?"

Réponse documentée dans le commit et ce changelog :
- `run_all_tests.py` T1–T8 : **simulation synthétique** (`ORICConfig` / `run_oric()`)
  → `test_type="statistical"` signifie "tests statistiques sur tirages simulés", PAS données réelles
- `run_real_data_canonical_suite.py` T1–T8 : **données observées réelles**
  → Granger, VAR, cointégration, bootstrap CI sur vraies séries temporelles

Pour la confirmation canonique protocolaire maximale, les DEUX suites doivent ACCEPT :
1. Suite synthétique → `full_statistical_support`
2. Suite données réelles → `real_data_canonical_support`

---

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
