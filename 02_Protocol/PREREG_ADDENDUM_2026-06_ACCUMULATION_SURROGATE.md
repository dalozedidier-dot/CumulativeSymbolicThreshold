# Pre-registration addendum — accumulation specificity & surrogate null

**Status:** FROZEN ex ante · **Date:** 2026-06-21 · **Applies to:** ORI-C v1.3+

This addendum freezes two confirmatory tests **before** any `full_statistical`
proof run that uses them. It responds to a structural objection: ORI-C's order
variable is an integrator,

```
C(t+1) = C(t) + β·S(t) − γ·V(t),
```

so any monotone driver `S` produces a growing, "self-reinforcing" `C`, and the
criterion `ΔC > μ + k·σ` (k = 2.5, m = 3) can fire from **accumulation** rather
than from a genuine **bifurcation**. Until ORI-C demonstrably classifies a smooth
saturation as *pre-threshold* and not *cumulative*, nothing distinguishes the
threshold detector from a trend detector.

## Exploratory vs confirmatory (governance)

All results currently in the repository — synthetic T1–T8, FRED, the 7 pilots,
the densified pilots — are **exploratory** (already run; some pre-date this
freeze). The tests below are **confirmatory** and must be evaluated on the frozen
criteria here, on systems retained *after* this date. Mixing the two is
prohibited; see `docs/EVIDENTIARY_STATUS.md`.

---

## Test A — Smooth-accumulation specificity

### Controls (frozen)

At least **3** smooth, monotone, saturating or trending, **non-bifurcating**
accumulation controls. The frozen set (`oric.accumulation_controls`):

1. `logistic_growth` — saturating S-curve (growth, **not** the chaotic map)
2. `gompertz` — asymmetric saturating growth
3. `exponential_saturation` — bounded exponential approach to an asymptote
4. `linear_ramp` — constant-rate monotone trend (no saturation, no break)

**Fair-design rule (frozen):** every control is quiescent during the
baseline-estimation window and exhibits its monotone rise in mid-series, so the
only systematic difference from a genuine bifurcation is *smoothness vs a
localized break* (`linear_ramp` is the deliberate "pure global trend" exception).

Contrast (positives): `sharp_regime_switch`, `delayed_bifurcation` — genuine
localized regime changes that the detector *should* flag.

### Statistic & criteria (frozen)

- `accumulation_fpr` = fraction of non-bifurcating accumulations on which the
  detector fires a **sustained** crossing (`ΔC > μ + k·σ` for `m` steps).
- Pass iff **`accumulation_fpr ≤ 0.25`** (`accumulation_fpr_max`, also enforced as
  the T9 `accumulation_specificity` sub-block on the 8-feature classifier).

### Falsification rule (frozen)

> If `accumulation_fpr > 0.25`, **H (threshold = genuine phase transition) is
> refuted in its current form**: ORI-C cannot be distinguished from a trend
> detector. If instead every smooth accumulation is rejected while genuine
> bifurcations are flagged, that separation is the strongest single piece of
> evidence for H.

### Runner

```
python 04_Code/pipeline/run_accumulation_control.py --outdir <out> --n-surrogates 200
```

---

## Test B — Surrogate null for threshold crossing (IAAFT)

### Procedure (frozen)

1. Run ORI-C on the real series → observed crossing statistic
   (`crossing_rate`, secondary `max_run`).
2. Generate **IAAFT** surrogates (Schreiber & Schmitz 1996) of each input channel
   (O, R, I, demand) independently — preserving the per-channel amplitude
   distribution **and** power spectrum (hence full linear autocorrelation), while
   destroying nonlinear and cross-channel phase structure.
3. Re-run the **same** detector on each surrogate.
4. Empirical one-sided p: `p = (1 + #{stat_surrogate ≥ stat_observed}) / (n+1)`.

`n_surrogates ≥ 500` for a confirmatory run.

### Criterion (frozen)

- The real crossing statistic is **confirmed** only if `p < 0.01`. A crossing rate
  that is not significant against the spectral null is attributable to the series'
  own autocorrelation, not to a transition.

### Runner

```
python 04_Code/pipeline/run_surrogate_null.py --input <real.csv> --outdir <out> --n-surrogates 500
```

---

## Test C — Specification curve / multiverse robustness

### Procedure (frozen)

Run ORI-C across a pre-declared grid of **equally defensible** analytic choices —
orthogonal to the frozen detector parameters (k, m, baseline_n):

- `normalize` ∈ {robust_minmax, zscore, minmax}
- `smooth` ∈ {none, ma3, ma5}
- `demand_to_cap_ratio` ∈ {0.85, 0.90, 0.95}

→ 27 specifications (`oric.multiverse.specification_grid`). For each, record whether
the sustained crossing fires and its crossing rate.

### Criterion (frozen)

- `ROBUST_POSITIVE` iff the detector fires in **≥ 80 %** of specifications;
  `ROBUST_NEGATIVE` iff **≤ 20 %**; otherwise **`FRAGILE`** — the verdict depends on
  an arbitrary proxy choice and **does not confirm**.
- Robustness is **necessary but not sufficient**: a `ROBUST_POSITIVE` that fails
  Test A (accumulation specificity) or Test B (surrogate null) is a robust *trend*,
  not a confirmed transition. Confirmation requires Test A reject + Test B p < 0.01
  + Test C `ROBUST_POSITIVE`.

### Runner

```
python 04_Code/pipeline/run_multiverse.py --input <real.csv> --outdir <out>
```

### Current outcome (exploratory)

- FRED monthly: `ROBUST_NEGATIVE` (0/27 fire on the default detector path).
- Pantheon SN densified: `ROBUST_POSITIVE` (27/27, rate 0.39–0.45) — **but** Test B
  gives p = 0.17 (n.s.): a robust trend, not a confirmed transition.

---

## Test D — Effect size vs SESOI + power (real-data reporting rule, frozen)

On real data the decision is **never** the p-value. For the order variable C
(post-threshold vs pre-threshold) report the standardised effect (in robust-SD
units) with its 99 % CI, against the frozen SESOI
(`sesoi_c_robust_sd = 0.30`), plus the achieved power
(`oric.effect_size.effect_size_report`; `run_effect_size_report.py`).

Verdict (frozen):
- `EFFECT_EXCEEDS_SESOI` iff the full 99 % CI lies beyond the SESOI (direct,
  power-independent evidence);
- else `UNDERPOWERED` iff power to detect the SESOI `< 0.70`
  (indeterminate — *not* absence of effect);
- else `EFFECT_BELOW_SESOI`.

**This is a magnitude statement, not a transition claim.** A large
`EFFECT_EXCEEDS_SESOI` on C is exactly what a trend/integrator produces; it
confirms a *transition* only in conjunction with Test A (reject) and Test B
(p < 0.01). Exploratory outcome: Pantheon SN C-jump = +0.89 robust-SD,
99 % CI [0.52, 1.35] → `EFFECT_EXCEEDS_SESOI` in magnitude, yet Test B gives
p = 0.17 → not a confirmed transition.

## Reporting denominator (frozen)

Real-data confirmation is reported as an **honest fraction**: *k of N
pre-specified systems crossed, of which j were predicted in advance* — never a
single hand-picked ACCEPT. Per-system **power** and **effect size vs SESOI** are
reported; the p-value alone is not reported for real data.

## Parameters held fixed

`k = 2.5`, `m = 3`, `baseline_n = 30`, `α = 0.01`, CI = 99 %. Any change requires a
new pre-registration. Seeds are logged in each run's `manifest.json`.
