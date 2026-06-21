# Evidentiary Status — honest accounting

**Last updated:** 2026-06-21

This document is the **single source of truth** for *what the ORI-C evidence
currently supports*, aligning the displayed verdicts with the real probative
state of the repository. Where other documents (README badges, `framework_status.md`,
manuscript §3.1) summarise verdicts, **this page governs their interpretation.**

> **One-line status:** the framework is a *built, falsifiable test machine* that is
> **exploratory / indicative**, not *solidly confirmed*. The decisive confirmatory
> controls are now implemented, and the bare detector **does not yet pass them**.

---

## 1. No `full_statistical` proof run exists

By the project's own governance rule (manuscript §2.3; `run_mode` field), a
publishable verdict requires a `full_statistical` run (N ≥ 50) carrying the
**obligatory triplet** — *p-value + CI₉₉ % + SESOI + power*.

- **There is no file in `05_Results/` with `run_mode: full_statistical`.** Every
  committed verdict was produced in `smoke_ci` mode or by the validation
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

## 3. The decisive controls — and the current (failing) outcome

Two confirmatory tests requested by external review are now implemented and
frozen ex ante (`02_Protocol/PREREG_ADDENDUM_2026-06_ACCUMULATION_SURROGATE.md`).
**Run honestly, the bare detector does not pass them.**

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
| `accumulation_fpr` (bare ΔC criterion) | **1.00** | every smooth accumulation flagged as a sustained "transition" |
| `bifurcation_tpr` | 1.00 | genuine bifurcations also flagged |
| `separates` | **False** | the criterion does **not** distinguish trend from transition |
| T9 8-feature classifier FPR on the same controls | **0.50** | the richer classifier is also confounded |

`logistic_growth` — a pure saturating S-curve with **no bifurcation whatsoever** —
produces a **70+ step sustained crossing**, indistinguishable from a genuine
regime switch. **Per the frozen rule (`accumulation_fpr > 0.25`), this refutes the
hypothesis in its current bare form:** the detector cannot be distinguished from a
trend detector.

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
**and** Test D (effect size) all pass. Run on the two headline ACCEPTs:

| Series | A (accum. fpr) | B (surrogate p) | C (multiverse) | D (effect/SESOI) | **Joint** |
|--------|----------------|-----------------|----------------|------------------|-----------|
| Pantheon SN | FAIL (1.0) | FAIL (p=0.17) | PASS (robust+) | PASS (exceeds) | **NOT_CONFIRMED** |
| FRED monthly | FAIL (1.0) | FAIL (p=1.0) | FAIL (robust−) | PASS (exceeds) | **NOT_CONFIRMED** |

Pantheon is robust to proxies and has a large C effect, but fails both
transition-specific controls. The **limiting factor is Test A** — a property of
the detector itself (the bare ΔC integrator), not of any one series — so **no
pilot can be confirmed until the detector distinguishes accumulation from
bifurcation.**

## 4. What "solidly confirmed" still requires

Implemented:
- ✅ Smooth non-bifurcating accumulation controls (`accumulation_controls.py`, T9)
- ✅ IAAFT surrogate null for threshold crossing (`surrogates.py`)
- ✅ **Specification-curve / multiverse** over defensible analytic choices (`multiverse.py`)
- ✅ **Effect size vs SESOI + achieved power** for real-data reporting (`effect_size.py`)
- ✅ Governance aligned to the real probative state (this document)
- ✅ Frozen ex-ante protocol separating exploratory from confirmatory

Multiverse outcome (exploratory): FRED `ROBUST_NEGATIVE` (0/27 specs fire);
Pantheon SN `ROBUST_POSITIVE` (27/27) — but n.s. against the surrogate null
(p = 0.17), i.e. a robust *trend*, not a confirmed transition. Robustness to
proxies is **necessary but not sufficient**: confirmation requires Test A reject +
Test B p < 0.01 + Test C `ROBUST_POSITIVE` jointly.

Joint confirmatory suite (`run_confirmatory_suite.py`) combines the controls under
the frozen joint rule; both headline ACCEPTs come out **NOT_CONFIRMED** (§3c).

Still outstanding (roadmap, not yet done):
- ⬜ **Fix the detector first** — a localized / de-trended transition statistic
  (e.g. concentration of ΔC change, slope-break detection) so Test A can pass.
  This is the prerequisite for every per-series confirmation below.
- ⬜ A `full_statistical` proof run storing the complete triplet (p + CI₉₉ % + SESOI + power)
- ⬜ A pre-registered **out-of-sample directional prediction** (T3 is `INDETERMINATE`).
  **Deliberately not shipped yet:** because C is an integrator, a naive OOS
  *crossing* prediction inherits the same trend confound as Test A and would
  demonstrate the confound rather than confirm a transition. It must be built on
  the localized statistic above (predict a *localized regime change*, not "C keeps
  rising"), evaluated against the accumulation-vs-bifurcation taxonomy.
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
