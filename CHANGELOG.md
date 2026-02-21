# Changelog

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
