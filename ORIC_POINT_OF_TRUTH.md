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

## Relation to ORI-C normative placard
This file is a repo-level anchor and must remain consistent with:
- ORI-C placard (normative v1.0)
- PREREG_TEMPLATE.md (all parameters fixed ex ante)
