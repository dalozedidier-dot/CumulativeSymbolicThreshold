# ORI-C Canonical Point of Truth

Version: 1.0
Date: 2026-02-17

This repository is the canonical implementation of the ORI-C normative framework and its decision protocol.

## Normative anchors
- ORI-C Pancarte Normative v1.0 (FR) and EN PDFs are the citation-ready normative summary.
- Decision protocol is fixed ex ante in `02_Protocol/DECISION_RULES_v2.md`.
- Pre-registration parameters and experiment manifests must be declared ex ante. See `02_Protocol/PREREG_TEMPLATE.md` if present, or use the fields listed in `02_Protocol/DECISION_RULES_v2.md`.

## Non negotiable constraints
- All functional forms, weights, windows, SESOI, alpha, and decision rules are fixed before observing the results.
- Results can be positive, null, or negative. All must be reported.
- One run equals one separate observation. Separation is enforced by distinct seeds and by full episode resets.

## Outputs and artifacts
- Raw run-level outputs: `05_Results/raw/`
- Derived summaries and verdicts: `05_Results/derived/`
- Registered report placeholders: `05_Results/registered_reports/`

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

## DOI
OSF project DOI: 10.17605/OSF.IO/G62PZ
