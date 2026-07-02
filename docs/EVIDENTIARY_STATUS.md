# Evidentiary Status — honest accounting

**Last updated:** 2026-07-01

This document is the **single source of truth** for *what the ORI-C evidence
currently supports*, aligning the displayed verdicts with the real probative
state of the repository. Where other documents (README badges, `framework_status.md`,
manuscript §3.1) summarise verdicts, **this page governs their interpretation.**

> **One-line status:** the framework is a *built, falsifiable test machine* that is
> **exploratory / indicative**, not *solidly confirmed*. The decisive confirmatory
> controls are now implemented. The old bare sustained ΔC crossing failed the trend control, so the current code adds a conservative localized-transition gate. This fixes Test A on the synthetic trend-vs-transition controls, but the headline real pilots remain **NOT_CONFIRMED** because the surrogate-null and multiverse gates still fail where applicable.

---

## 1. `full_statistical` proof run — synthetic demonstration now exists; real pilots still pending

By the project's own governance rule (manuscript §2.3; `run_mode` field), a
publishable verdict requires a `full_statistical` run (N ≥ 50) carrying the
**obligatory triplet** — *p-value + CI₉₉ % + SESOI + power*.

- **A `full_statistical` run now exists for the endogenous bistable demonstration
  model** (`05_Results/endogenous_full_statistical/`,
  `run_endogenous_full_statistical.py`, N = 50): the critical-slowing-down effect
  of the bistable fold approach vs its matched linear twin is
  `standardised_effect ≈ +1.13`, 99 % CI `[+0.83, +1.82]` (entirely beyond the
  frozen SESOI 0.30 ⇒ `EFFECT_EXCEEDS_SESOI`), Mann–Whitney `p ≈ 1.4e-10`, with
  twin false-positive rate 0.08 ≤ the 0.20 ceiling. This is a demonstration on a
  model that genuinely instantiates a bifurcation (see §3d), not yet a real-pilot
  confirmation.
- **No real-data pilot has a `run_mode: full_statistical` run.** Every committed
  *real-pilot* verdict was produced in `smoke_ci` mode or by the validation
  protocol, neither of which stores the triplet.
- Synthetic p-values such as `2.6e-301` or `8.9e-51` are **artefacts of very large
  N**; without an effect size against a pre-declared SESOI they carry no
  evidential weight.
- Manuscript §3.1 already labels every T1–T8 verdict *« indicatif — à confirmer »*.
  The README/`framework_status.md` headline `ACCEPT — full_statistical_support`
  **over-claimed** relative to this and has been corrected to match.

## 2. Real data is mixed, and the one ACCEPT is fragile

Of the three **densified** real pilots (`05_Results/real_validation/`):

| Pilot | Verdict | Note |
|-------|---------|------|
| `pantheon_sn` | **ACCEPT** | **config-fragile** — see below |
| `pbdb_marine` | **REJECT** | no transition detected (det_rate 0.0) |
| `llm_scaling` | **REJECT** | no transition detected (det_rate 0.0) |

The single ACCEPT inverts entirely with configuration
(`pilot_pantheon_sn_densified/tables/validation_summary.json`):

- **`test` config:** 15/15 detected (detection_rate 1.0)
- **`stable` config:** 0/15 detected (detection_rate 0.0, `sigma_zero_post_rate` 1.0)

A detection that flips from 100 % to 0 % across configurations is **not a robust
signature**. The broader 7-pilot benchmark (5 ACCEPT / 2 REJECT) is entirely
**Level B, borderline power, no Level A canonical proof run**.

## 3. The decisive controls and the current outcome

Two confirmatory tests requested by external review are now implemented and
frozen ex ante (`02_Protocol/PREREG_ADDENDUM_2026-06_ACCUMULATION_SURROGATE.md`).
The old bare detector failed the accumulation control. The current code now records both values: `raw_detector_fired` for audit continuity and `detector_fired` for the conservative localized-transition gate.

### 3a. Smooth-accumulation specificity (trend vs transition)

ORI-C's order variable is an integrator, `C(t+1) = C(t) + β·S − γ·V`, so *any*
monotone driver produces a growing, "self-reinforcing" `C`. The original T9
negative controls (white/pink/red noise, random walk, sinusoid, Poisson,
chaotic map) are all stationary/oscillatory/chaotic and cannot separate the
hypothesis (a *bifurcation* detector) from its trivial rival (a *trend*
detector).

Four smooth, monotone, **non-bifurcating** accumulations (logistic growth,
Gompertz, exponential saturation, noisy linear ramp) were added. Result
(`05_Results/falsification/accumulation_control/`, `run_accumulation_control.py`):

| Metric | Value | Meaning |
|--------|-------|---------|
| `raw_accumulation_fpr` (old bare ΔC criterion) | **1.00** | every smooth accumulation is still flagged by the old sustained-crossing rule |
| `accumulation_fpr` (localized gate) | **0.00** | smooth accumulations are rejected by the current conservative transition gate |
| `bifurcation_tpr` (localized gate) | **1.00** | the two synthetic bifurcations remain detected |
| `separates` | **True** | the current gate separates smooth accumulation from localized bifurcation on this control catalogue |

`logistic_growth` remains the audit warning case: the old bare sustained ΔC crossing still fires on a pure saturating S-curve with no bifurcation. The new gate therefore keeps `raw_detector_fired` visible, but makes `detector_fired` depend on temporal localization of the change. This is a code-level correction of the trend-detector confound, not yet a full empirical confirmation of ORI-C on real data.

### 3b. Surrogate null for the threshold crossing (IAAFT)

"`N/M` steps exceed the threshold" has no meaning without a null law. We compute
the crossing statistic on the real series and on **IAAFT surrogates** (Schreiber &
Schmitz 1996) that preserve, per channel, the amplitude distribution **and** the
power spectrum (hence the full linear autocorrelation). Result
(`05_Results/surrogate_null/`, `run_surrogate_null.py`):

| Series | observed crossing rate | IAAFT null mean (q99) | empirical p | α=0.01 |
|--------|------------------------|-----------------------|-------------|--------|
| FRED monthly | 0.00 | 0.14 (0.48) | 1.00 | n.s. |
| Pantheon SN (densified) | 0.42 | 0.14 (0.52) | **0.17** | **n.s.** |

Pantheon's crossing rate looks high, but a spectrally matched surrogate reaches it
~17 % of the time: **the crossing is not distinguishable from the series' own
autocorrelation** at α = 0.01.

## 3c. Joint confirmatory verdict — both headline ACCEPTs are NOT_CONFIRMED

The four controls are combined under a frozen joint rule
(`oric.confirmatory`, `run_confirmatory_suite.py`): a series is **CONFIRMED** only
if Test A (global) **and** Test B (surrogate null) **and** Test C (multiverse)
**and** Test D (effect size) all pass. A full rerun (500 IAAFT surrogates per series, stored
under `05_Results/confirmatory/`) after the localized-gate correction gives:

| Series | A (accum. fpr) | B (surrogate p) | C (multiverse) | D (effect/SESOI) | **Joint** |
|--------|----------------|-----------------|----------------|------------------|-----------|
| Pantheon SN | PASS (0.0) | FAIL (p≈0.17) | PASS (robust+) | PASS (exceeds) | **NOT_CONFIRMED** |
| FRED monthly | PASS (0.0) | FAIL (p=1.0) | FAIL (robust−) | PASS (exceeds) | **NOT_CONFIRMED** |

Pantheon is robust to proxies and has a large C effect, and Test A now passes after the localized-gate correction. It still fails the surrogate-null gate, so it should be described as a robust signal or promising pilot, not as confirmed evidence of a transition. FRED remains not confirmed because it fails the surrogate-null and multiverse gates.

## 3d. Endogenous mechanism — the model now instantiates a genuine bifurcation

The original simulator has **no state-dependent feedback** (`S` is a leaky
integrator of an exogenous Σ; `C` a cumulative sum of `S`), so it cannot produce
a fold, hysteresis or critical slowing down endogenously — any "bifurcation" was
a steep curve imposed on the `demand` input, and the detector only separated
"steep step" from "smooth ramp" on that input. `oric.endogenous` adds the missing
positive feedback (`dC/dt = a − b·C + r·C^p/(C^p+h^p)`, May 1977; Scheffer 2009),
giving a true saddle-node with two stable branches over a window of the control
parameter `a = a0 + g·S`. The matched **linear twin** (feedback off, `r=0`) is the
decisive negative control: same drive, start and noise, no fold.

`oric.early_warning` then makes **critical slowing down the primary detector**
(rising lag-1 autocorrelation and variance), with significance assessed against a
**trend-preserving surrogate null** (`oric.surrogates.trend_preserving_surrogate`)
that keeps the trend and residual spectrum but destroys the localized rupture —
FPR controlled at the nominal level on clean trend+AR(1) nulls.

The `full_statistical` demonstration (§1; `05_Results/endogenous_full_statistical/`)
confirms, over N = 50, that the bistable approach beats its linear twin on this
detector with a large effect whose 99 % CI lies entirely beyond the SESOI, while
the twin's false-positive rate stays under the frozen ceiling — and corroborates
with a hysteresis loop (area 3.67 vs 0.36) and a steady-state discontinuity at the
fold (jump 2.48 vs 0.0). This shows the framework's *mechanism* is now
demonstrable; it does not by itself confirm ORI-C on real data.

## 4. What "solidly confirmed" still requires

Implemented:
- ✅ Smooth non-bifurcating accumulation controls (`accumulation_controls.py`, T9)
- ✅ IAAFT surrogate null for threshold crossing (`surrogates.py`)
- ✅ **Specification-curve / multiverse** over defensible analytic choices (`multiverse.py`)
- ✅ **Effect size vs SESOI + achieved power** for real-data reporting (`effect_size.py`)
- ✅ Governance aligned to the real probative state (this document)
- ✅ Frozen ex-ante protocol separating exploratory from confirmatory
- ✅ **Strong-negatives specificity battery** with stored artifact
  (`05_Results/strong_negatives/`, `run_strong_negatives.py`):
  `STRONG_NEGATIVES_CLEAN` — the localized gate fires on **0/11** adversarial
  non-transition processes (unit-root random walk, AR(1) red noise, 1/f noise,
  sinusoid, sawtooth, smooth accumulations) while the legacy bare gate leaks on
  54.5 %, and both genuine bifurcations are still flagged (TPR 1.0).
- ✅ **Registered real-data A/B/C block** with stored artifact
  (`05_Results/registered_block/`, frozen ex ante in
  `contracts/REAL_DATA_REGISTRATION.json`): **`REAL_BLOCK_REJECTED`** — an honest
  registered negative. ORI-C does not fire on FRED/GFC (crossing 0.0, IAAFT
  p = 1.0) yet is *specific*: silent on the stable and placebo controls while the
  classical panel (CUSUM/PELT/EWS/structural break) false-fires 8× on them.

Multiverse outcome (exploratory): FRED `ROBUST_NEGATIVE` (0/27 specs fire);
Pantheon SN `ROBUST_POSITIVE` (27/27) — but n.s. against the surrogate null
(p = 0.17), i.e. a robust *trend*, not a confirmed transition. Robustness to
proxies is **necessary but not sufficient**: confirmation requires Test A reject +
Test B p < 0.01 + Test C `ROBUST_POSITIVE` jointly.

Joint confirmatory suite (`run_confirmatory_suite.py`) combines the controls under
the frozen joint rule; after the detector correction, both headline ACCEPTs still come out **NOT_CONFIRMED** (§3c).

Still outstanding (roadmap, not yet done):
- ✅ **Detector correction added**: the current code uses a localized-transition gate and keeps the old bare ΔC crossing as `raw_detector_fired` for audit continuity. Test A now separates the shipped synthetic accumulation controls from the shipped bifurcation controls.
- ✅ Re-run the confirmatory suite in non-fast mode with high surrogate counts and store the resulting artefacts under `05_Results/` (done — `05_Results/confirmatory/{pantheon_sn,fred_monthly}/`, 500 IAAFT surrogates, seed 1234; Test A now PASS, joint still NOT_CONFIRMED).
- ✅ A `full_statistical` proof run storing the complete triplet (p + CI₉₉ % + SESOI + power)
  — done for the **endogenous bistable demonstration** model
  (`05_Results/endogenous_full_statistical/`, N = 50; §1, §3d). A real-pilot
  `full_statistical` run remains outstanding.
- ✅ A pre-registered **out-of-sample directional prediction** — now shipped and
  run under the frozen protocol
  (`02_Protocol/PREREG_OOS_2026-06_LOCALIZED_TRANSITION.md`,
  `contracts/OOS_PREREG.json`). Built, as required, on the *localized* statistic
  (trend-preserving CSD surrogate null — predict a *localized regime change*, not
  "C keeps rising"), so it does not inherit the integrator/trend confound.
  **Outcome of the confirmatory run** (frozen `lead = 60`, N = 50, stored in
  `05_Results/oos_prediction/`): TPR 0.14 vs twin FPR 0.04, Fisher p ≈ 0.08 →
  **`OOS_SKILL_INCONCLUSIVE`** — an honest negative at equal status to a positive
  (per-trajectory CSD prediction is modest-power at short lead; Boettiger &
  Hastings 2012). The pre-freeze exploratory run (`lead = 40`) is preserved
  verbatim under `05_Results/oos_prediction/exploratory_lead40_prefreeze/`.
  The secondary FRED forward prediction (Part B) remains **registered, pending**
  — frozen before scoring, untouched.
- ⬜ Column-level proxy alternatives in the multiverse (k interchangeable source columns per variable, where available)
- ⬜ Independent third-party replication via the Docker/Zenodo bundle

## 5. Reproduce

```bash
pip install -e ".[dev]"

# Decisive trend-vs-transition control (smooth accumulation vs bifurcation)
python 04_Code/pipeline/run_accumulation_control.py \
  --outdir 05_Results/falsification/accumulation_control --n-surrogates 200

# IAAFT surrogate null on a real pilot
python 04_Code/pipeline/run_surrogate_null.py \
  --input 03_Data/sector_cosmo/real/pilot_pantheon_sn/real_densified.csv \
  --outdir 05_Results/surrogate_null/pantheon_sn --n-surrogates 500

# T9 with the accumulation-specificity block
python 04_Code/pipeline/run_T9_cross_domain.py --outdir 05_Results/t9 --fast
```

## Cap(t) robustness note

`Cap(t)` is treated as an ex-ante structural specification rather than a final theoretical truth. Structural conclusions involving `Sigma(t)`, overload, viability or collapse thresholds should be checked against declared alternative forms. See `docs/CAP_ROBUSTNESS.md` and `contracts/CAP_ROBUSTNESS.json`.
