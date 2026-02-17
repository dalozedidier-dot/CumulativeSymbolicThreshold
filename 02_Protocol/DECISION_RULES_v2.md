# Decision Rules ORI-C
Version: 2.0
Date: 2026-02-17

This document is normative. It defines the decision protocol used to produce local verdicts and global verdicts.

## 1. Global conventions
- Significance level: alpha = 0.01.
- Confidence intervals: 99% intervals aligned with alpha.
- Each test reports the triplet: p-value, 99% CI, SESOI.
- Verdicts are local per test, then aggregated into global verdicts for the ORI core and for the symbolic layer.

### Verdict labels
- ACCEPT: evidence supports the hypothesis and the observed effect is at least SESOI, with adequate quality and power.
- REJECT: evidence contradicts the hypothesis with adequate quality and power, or effect direction is opposite and exceeds SESOI in the opposite direction.
- INDETERMINATE: quality gate failed, power gate failed, or evidence is insufficient relative to SESOI.

## 2. SESOI
SESOI are fixed ex ante and stable across runs.

- Cap: SESOI_Cap = +10% relative to baseline.
- V: SESOI_V = -10% relative to baseline on V_q05 computed on a fixed window W.
- C: SESOI_C = +0.30 robust SD (MAD based) relative to baseline.

Baseline is declared ex ante. Default baseline is the minimal condition for ORI and S, unless another baseline is explicitly preregistered.

## 3. Independence and minimal sample size
- One run equals one independent observation. Independence is enforced through distinct seeds and full episode resets.
- Minimal N per condition: N_min = 50 valid runs.

## 4. Quality gate
The quality gate is applied before any statistical decision.

Gate passes only if all conditions are met:
1) Technical failure rate < 5%.
2) For each condition, at least N_min valid runs.
3) No missing critical columns in the run-level table.
4) Series summaries are computed with fixed windows and no post-hoc changes.

If the gate fails: all local verdicts are INDETERMINATE, and the global verdict is INDETERMINATE.

## 5. Power gate
Power is evaluated at the SESOI level.

- Target power: 80% at SESOI.
- If estimated power < 70% for a test: local verdict is forced to INDETERMINATE, even if p <= 0.01.

Default power estimation method:
- Bootstrap based power using the observed noise model and SESOI injected effect, with B = 500 resamples.
This must be fixed ex ante. If another method is used, it must be preregistered.

## 6. Run-level derived metrics
Run-level series are summarized using fixed rules.

Required metrics per run:
- Cap_star: capacity estimate from a standardized ramp procedure, or from a declared proxy if ramp is not applicable.
- V_q05: 5th percentile of performance on a fixed window W.
- A_sigma: cumulative mismatch area, sum of Sigma(t) over the run.
- frac_over: fraction of timesteps where Sigma(t) > 0.
- C_gen: inter-generation gain computed on an early window, or a declared analog if generations are not explicit.

## 7. Local decision templates
Each local test yields:
- effect estimate, standardized effect if applicable
- p-value
- 99% CI
- power estimate at SESOI
- local verdict

A local ACCEPT requires:
- quality gate pass
- power >= 70%
- p <= 0.01
- effect size meets SESOI in the expected direction

A local REJECT requires:
- quality gate pass
- power >= 70%
- effect size exceeds SESOI in the opposite direction, and p <= 0.01

Otherwise: INDETERMINATE.

## 8. Aggregation logic
### ORI core
Accept ORI core if:
- Test1 ACCEPT and Test2 ACCEPT and Test3 ACCEPT
or
- Test1 ACCEPT and Test2 ACCEPT and Test3 INDETERMINATE due to power < 70%

Reject ORI core if:
- Any test is REJECT with adequate power and effect direction is contradictory.

Otherwise: INDETERMINATE.

### Symbolic layer
Accept symbolic layer if:
- Test4 ACCEPT and at least one of Test5, Test6, Test7 is ACCEPT, and none is REJECT.

Reject symbolic layer if:
- Test7 REJECT with adequate power and Test4 is not ACCEPT
or
- Test4 REJECT with adequate power.

Otherwise: INDETERMINATE.

## 9. Required outputs
The analysis produces:
- `verdicts_local.csv`
- `verdicts_global.json`
- `diagnostics.md` with gate results and summary statistics.

