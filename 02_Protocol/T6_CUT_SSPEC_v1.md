# T6-cut and SSpec
Version: 1.0
Date: 2026-09-29
Status: additive protocol — does not amend DECISION_RULES_v2 frozen numbers

Implementation notice: the single-series verdict interpretation below is
superseded by `docs/T6_SENSITIVITY_GATE.md`. Retrospective S transformations
now report INDETERMINATE only. They cannot establish causal ACCEPT or REJECT.

## Purpose
T6 claims the symbolic layer is irreducible to O, R, I.
This addendum states the missing operational condition: S must be a
transmissible stock with a declared copy rule and a declared cut rule.

## SSpec (required for symbolic-layer ACCEPT)
A pilot may reach ACCEPT on the symbolic layer only if an `SSpec` is
logged (SHA-256 in the run manifest) and `validate()` passes.

Required fields:
- `kind`: lineage | vesicle | code | language | institution
- `source_column`: distinct from O, R, I, Cap, Sigma, V
- `copy_rule`: how S moves from bearer t to bearer t+1
- `cut_rule`: how transmission is interrupted without destroying the system
- `cut_operator`: zero | permute | delay | reset_generation

If SSpec is missing or invalid: local T6 verdict is INDETERMINATE.

Forbidden S:
- any transform of the same series used for Cap
- variance, autocorrelation, entropy of Cap
- narrative / coherence scores without a copy rule

## T6-cut arms
1. intact — original S
2. cut — `cut_operator` applied to S only
3. sham — permute V or Cap, leave S intact

C is computed with the existing `compute_order_C` (no new functional form).
SESOI_C remains +0.30 robust SD (MAD × 1.4826), as in DECISION_RULES_v2.

## Local verdict
- ACCEPT: C collapses under cut (Δ ≥ SESOI_C) and not under sham (Δ < SESOI_C)
- REJECT: C does not collapse under the declared cut, with finite contrasts
- INDETERMINATE: short series, invalid spec, or contrasts not separable

Quality and power gates of DECISION_RULES_v2 still apply to multi-run
experiments. The helper `run_t6_cut` is a series-level diagnostic; it does
not bypass N_min = 50 for a confirmatory claim.

## Recommended first pilot
S-first living system (lineage or vesicle), not FRED / solar / EEG.
A clean REJECT on a real S channel is more informative than an ACCEPT
on a series with no copy rule.
