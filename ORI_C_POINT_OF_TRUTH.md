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
- One run equals one independent observation. Independence is enforced by seeds and by full episode resets.

## Outputs and artifacts
- Raw run-level outputs: `05_Results/raw/`
- Derived summaries and verdicts: `05_Results/derived/`
- Registered report placeholders: `05_Results/registered_reports/`

## DOI
OSF project DOI: 10.17605/OSF.IO/G62PZ
