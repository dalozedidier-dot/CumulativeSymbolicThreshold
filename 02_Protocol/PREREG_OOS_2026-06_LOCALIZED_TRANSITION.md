# Pre-registration — out-of-sample directional prediction of a *localized* regime change

**Status:** FROZEN ex ante · **Freeze date:** 2026-06-22 · **Applies to:** ORI-C v1.3+
**Machine-readable twin:** [`contracts/OOS_PREREG.json`](../contracts/OOS_PREREG.json)

This document freezes a confirmatory **out-of-sample (OOS) prediction** *before*
its confirmatory outcome is known, so the verdict cannot be tuned after the fact.
It is the rung-8 entry of [`docs/EVIDENCE_LADDER.md`](../docs/EVIDENCE_LADDER.md).

## Why this prediction is shaped the way it is

ORI-C's order variable is an integrator, `C(t+1) = C(t) + β·S − γ·V`. So a naive
OOS prediction of the form *"C will keep rising / cross the threshold"* is
**trivially true** for any monotone driver and would merely re-demonstrate the
trend confound (see Test A in `PREREG_ADDENDUM_2026-06_ACCUMULATION_SURROGATE.md`).

The registered prediction is therefore explicitly about a **localized regime
change** — a critical-slowing-down signature (rising lag-1 autocorrelation and
variance) that culminates in a rupture — assessed from the **run-up window
alone**, against a **trend-preserving surrogate null** that keeps the trend and
residual spectrum but destroys the localized rupture. Predicting *where the break
is*, not *that the level grows*, is what separates a transition detector from a
trend detector.

---

## Part A — Primary, decisive prediction (synthetic, runnable now)

### Design (frozen)

For each of **N = 50** matched replicates we generate a pair:

- a **bistable** endogenous fold (`oric.endogenous`, saddle-node), and
- its **matched linear twin** (feedback off, `r = 0`) — same drive, start and
  noise, **no fold**. The twin is the negative control: any prediction it
  triggers is a false alarm.

The predictor sees **only** `C[0 : jump − lead]` (the pre-event run-up). It must
decide, from that window alone, whether a localized transition is coming.

### Frozen parameters

| Parameter | Value | Source |
|---|---|---|
| `seed_base` | 7000 | `oric.frozen_params.FROZEN_PARAMS` |
| `n_replicates` | 50 | `FROZEN_PARAMS` |
| `n_surrogates` | 99 | this prereg |
| `lead` (hold-out before jump) | 60 | this prereg |
| `alpha` (prediction) | 0.05 | this prereg |
| `n_steps` | 1500 | this prereg |
| `noise_sd` | 0.05 | this prereg |
| `timing_tolerance` | 500 | this prereg |

### Statistic & decision rule (frozen)

- Predictor: `oric.oos_prediction.predict_transition` — trend-preserving CSD
  surrogate null; **predict a transition iff surrogate-null `p < alpha`**.
- Score: `oric.oos_prediction.score_prediction` → `hit` / `miss` /
  `false_alarm` / `correct_rejection`.
- Aggregate: `bistable_tpr` (over the folds) and `twin_fpr` (over the twins);
  one-sided **Fisher exact** test that skill is above chance.

> **Verdict (frozen):**
> `OOS_SKILL_DEMONSTRATED` **iff** `bistable_tpr > twin_fpr` **and**
> Fisher exact one-sided `p < 0.05`. Otherwise `OOS_SKILL_INCONCLUSIVE`.

`OOS_SKILL_INCONCLUSIVE` is **not** evidence of absence: per-trajectory CSD
prediction is known to be modest-power at short lead (Boettiger & Hastings 2012).
It is reported at equal status to a positive.

### Runner

```bash
python 04_Code/pipeline/run_oos_prediction.py \
  --outdir 05_Results/oos_prediction \
  --n-replicates 50 --n-surrogates 99 --lead 60 --alpha 0.05
```

### Honest exploratory outcome **before** this freeze

A pre-freeze exploratory run (`05_Results/oos_prediction/`, `lead = 40`) gave
`bistable_tpr = 0.14`, `twin_fpr = 0.06`, Fisher `p = 0.16` →
**`OOS_SKILL_INCONCLUSIVE`**. This pre-freeze result **does not count** as
confirmation; the frozen `lead = 60` protocol above governs the confirmatory run.

---

## Part B — Secondary, real-data forward prediction (registered, pending)

A genuine registered prediction on real data, frozen here **before** it is scored.

- **Dataset:** `03_Data/real/fred_monthly/real.csv`.
- **Split (frozen):** train = first 70 % of the series (index order); test =
  final 30 %, **held out and untouched until scoring**.
- **Prediction (frozen):** apply the **same localized predictor** to the training
  window only; a positive call is scored against whether a localized regime change
  occurs in the held-out window.
- **Rule (frozen):** the split, predictor and decision rule may **not** be changed
  to fit the outcome. Evaluation must use the localized predictor — **never** a
  naive crossing.
- **Status:** `REGISTERED_PENDING`. Committing the rule and split before the
  result is the pre-registration; the scored evaluation is future work.

---

## Parameters held fixed

`k = 2.5`, `m = 3`, `baseline_n = 50` (detector), `alpha = 0.05` (prediction),
`lead = 60`, `n_surrogates = 99`, `seed_base = 7000`, `n_replicates = 50`. Any
change requires a **new dated pre-registration**; this file is append-only by
supersession.
