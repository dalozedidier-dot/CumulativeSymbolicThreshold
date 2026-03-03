# ORI-C Canonical Point of Truth

**Version:** 1.1
**Date:** 2026-03-03
**Status:** CANONICAL — `ORIC_POINT_OF_TRUTH.md` is a backwards-compatibility alias for this file.

---

## 1. Normative anchors

- ORI-C Pancarte Normative v1.0 (FR) and EN PDFs (`docs/publications/`) are the citation-ready normative summary.
- Decision protocol is fixed ex ante in `02_Protocol/DECISION_RULES_v2.md`.
- Pre-registration parameters and experiment manifests must be declared ex ante.
  See `02_Protocol/PREREG_TEMPLATE.md` or the fields listed in `02_Protocol/DECISION_RULES_v2.md`.

## 2. Non-negotiable constraints

- All functional forms, weights, windows, SESOI, alpha, and decision rules are fixed **before** observing results.
- Results can be positive, null, or negative — all must be reported.
- One run equals one separate observation. Separation is enforced by distinct seeds and full episode resets.
- Parameter changes require a new pre-registration.

## 3. Outputs and artifacts

| Path | Content |
|------|---------|
| `05_Results/raw/` | Raw run-level outputs |
| `05_Results/derived/` | Derived summaries and verdicts |
| `05_Results/registered_reports/` | Registered report placeholders |

## 4. Decision commitments (ex ante)

| Parameter | Value |
|-----------|-------|
| Significance level α | 0.01 (non-negotiable) |
| Confidence intervals | 99% |
| Decision basis | Triplet: {p-value, CI, SESOI} |
| SESOI — Cap* | +10% relative vs baseline (or +0.5 robust SD via MAD) |
| SESOI — V (low-quantile) | −10% relative vs baseline (or −0.5 robust SD via MAD) |
| SESOI — C (intergenerational) | +0.3 robust SD via MAD |
| N_min per condition | 50 valid runs (100 preferred for stable power) |
| Power gate | Power < 0.70 → forced INDETERMINATE |
| Verdict tokens | `ACCEPT` / `REJECT` / `INDETERMINATE` |

**Quality gate (global):**
- Technical failure rate < 5 %
- At least N_min valid runs per condition
- Diagnostics OK (no divergence patterns, no data leakage)

**Welch-NaN fallback (normative, `WELCH_NAN_FALLBACK_POLICY`):**
Welch unavailable → bootstrap CI → Mann-Whitney U → INDETERMINATE. Never a silent default failure.

## 5. Falsifiability criteria

- **T1 + T2 + T3** validates the ORI–Cap–Σ–V core.
- **T4 + T5 + T7** validates the cumulative symbolic regime.
- **T6** confirms the symbolic dimension is irreducible to O, R, I alone.

See `02_Protocol/DECISION_RULES_v2.md` for the complete decision table.

## 6. DOI and citation

- OSF project DOI: `10.17605/OSF.IO/G62PZ`
- Pre-registration: <https://osf.io/g62pz/>
- See `CITATION.cff` for the full machine-readable citation.

## 7. Repository structure summary

```
CumulativeSymbolicThreshold/
├── 01_Theory/              Normative placard, theory, glossary
├── 02_Protocol/            Pre-registration, decision rules, intervention catalog
├── 03_Data/                Synthetic + real datasets with proxy_spec.json
├── 04_Code/
│   ├── pipeline/           All executable pipeline scripts
│   ├── tests/              Pytest unit and integration tests
│   └── configs/            JSON run configs
├── 05_Results/             Run outputs (gitignored)
├── 06_Manuscript/          Academic manuscript draft
├── docs/
│   ├── maintenance/        Operational notes and checkup logs
│   └── publications/       PDF/DOCX publications and manifestos
├── examples/               Jupyter notebooks (3 demos)
└── src/oric/               Importable Python package (pip install -e .)
```
