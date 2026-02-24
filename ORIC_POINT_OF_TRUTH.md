# ORI-C Point of Truth (Normative)

Version: 1.0
Date: 2026-02-17
Scope: Canonical repo conventions for decision, outputs, and reproducibility.

## Decision commitments (ex ante)
- Significance level: alpha = 0.01 (decision level).
- Decision basis: triplet {p-value, confidence interval, SESOI}.
- SESOI (fixed conventions, can be overridden only in prereg):
  - Cap*: +10% relative vs baseline (or +0.5 robust SD via MAD).
  - V (low-quantile): -10% relative vs baseline (or -0.5 robust SD via MAD).
  - C (inter-generational): +0.3 robust SD via MAD.
- Minimum runs per condition: N_min = 50 valid runs (default). Prefer N=100 for stable power.
- Power gate: if estimated power < 0.70 at SESOI, local verdict is forced to INDETERMINATE.
- Quality gate (global):
  - Technical failure rate < 5%.
  - At least N_min valid runs per condition.
  - Diagnostics OK (no obvious divergence patterns, no data leakage).

## Canonical outputs
All executable tests must write (inside their outdir):
- tables/summary.csv (one-row summary, includes a column 'verdict').
- verdict.txt (single token: ACCEPT, REJECT, or INDETERMINATE).
- figures/ (PNG figures, optional but recommended).

## Canonical orchestrators
- 04_Code/pipeline/run_canonical_suite.py: runs the canonical test suite and writes results under 05_Results/canonical_runs/<run_id>/.
- 04_Code/pipeline/analyse_verdicts_canonical.py: aggregates local verdicts into a global verdict using the decision tree.

## Welch-NaN fallback policy (normative, fixed ex ante)

When the Welch t-test p-value is NaN (series too short, zero variance, or numerical failure)
the decision procedure falls back in this fixed order. This behaviour is locked and must NOT
change post-observation:

  1. Block bootstrap CI (bootstrap_fallback) — if CI lower bound > 0 (direction-sensitive)
  2. Mann-Whitney U   (mannwhitney_fallback) — if MWU p-value is finite
  3. INDETERMINATE    (unavailable)          — when all three are unavailable

Verdict tokens for the "unavailable" case:
- `indetermine_stats_indisponibles` — threshold detected but all p-sources are NaN.
  Not a falsification. The run is preserved in the audit log.
- `indetermine_sigma_nul` — Sigma(t)≡0 post-threshold; symbolic canal inoperable.

The canonical implementation is `src/oric/decision.py:WELCH_NAN_FALLBACK_POLICY`.
`04_Code/pipeline/tests_causaux.py` must implement the identical cascade.

## Artefacts éphémères (zéro versionnement)

Les répertoires suivants sont gitignorés et NE DOIVENT PAS être committés:
  _ci_out/  _demo_out/  _tmp_results_ci/  _tmp*/  05_Results/

Si l'un d'eux est suivi (git ls-files | grep _ci_out), le retirer immédiatement:
  git rm -r --cached <dir>

## Relation to ORI-C normative placard
This file is a repo-level anchor and must remain consistent with:
- ORI-C placard (normative v1.0)
- PREREG_TEMPLATE.md (all parameters fixed ex ante)
