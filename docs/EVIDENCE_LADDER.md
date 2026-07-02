# Evidence ladder — ORI-C

**Status:** FROZEN ordering · **Last reviewed:** 2026-07-01 · **Companion of**
[`EVIDENTIARY_STATUS.md`](EVIDENTIARY_STATUS.md)

A claim about ORI-C is only as strong as the **highest rung it has actually
cleared**, and every rung has a machine-checkable gate. This page fixes the
ordering once, so no document can quietly promote a low rung to a high one.
`EVIDENTIARY_STATUS.md` records *where we are today*; this page defines *what each
level means and how to earn it*.

> **Golden rule.** A run reports the token of the rung it cleared — never a higher
> one. The strings `full support` and `full empirical support` are **not** rungs
> on this ladder and are forbidden in any report (enforced by the nightly).

## The ladder (weakest → strongest)

| # | Rung | Gate that must pass | Machine token | Runner |
|---|------|---------------------|---------------|--------|
| 0 | **Mechanism plausibility** | A model that *instantiates* a genuine bifurcation (saddle-node + linear twin), not a steep input. | `oric.endogenous` builds it | `run_endogenous_full_statistical.py` |
| 1 | **Smoke / runs-at-all** | Pipeline executes; verdict object is well-formed. Indicative only. | `run_mode: smoke_ci` → `smoke_ci_accept` | `run_all_tests.py --fast` |
| 2 | **Synthetic indicative** | T1–T8 ACCEPT in non-statistical mode. *« indicatif — à confirmer »*. | T-verdict `ACCEPT` (no triplet) | `run_all_tests.py` |
| 3 | **Synthetic full-statistical demonstration** | N ≥ 50 with the **triplet**: p + CI₉₉ % + SESOI + power ≥ 0.70, twin FPR ≤ 0.20. | `run_mode: full_statistical` → `full_statistical_support` | `run_endogenous_full_statistical.py`, nightly |
| 4 | **Real-data exploratory pilot** | A real series runs; Level B, borderline power. Single ACCEPTs may be config-fragile. | pilot `ACCEPT`/`REJECT` (Level B) | `run_real_data_demo.py` |
| 5 | **Real-data canonical** | Granger S→ΔC, VAR, cointegration C–S, bootstrap CI, threshold — CORE **and** SYMBOLIC accept. | `run_mode: real_data_canonical` → `real_data_canonical_support` | `run_real_data_canonical_suite.py`, nightly |
| 6 | **Confirmed transition** | **Joint** rule, all four + negatives + OOS (see below). | confirmatory `CONFIRMED` | `run_confirmatory_suite.py` (+ 7, 8) |
| 5–6 | **Registered real-data A/B/C block** | One frozen-ex-ante block: A (test, dated transition) detected + B (stable) & C (placebo) silent + IAAFT surrogate `p<0.01` + classical-panel comparison + real OOS. | `REAL_BLOCK_CONFIRMED` | `run_registered_block.py` (against `contracts/REAL_DATA_REGISTRATION.json`) |
| 7 | **Strong-negatives clean** | The pre-registered strong-negatives battery does **not** fire (specificity). | `STRONG_NEGATIVES_CLEAN` | `run_strong_negatives.py` |
| 8 | **Pre-registered out-of-sample skill** | A *frozen-before-outcome* directional prediction shows positive, specific skill above the surrogate chance level. | `OOS_SKILL_DEMONSTRATED` | `run_oos_prediction.py` (against `02_Protocol/PREREG_OOS_*`) |
| 9 | **Independent external replication** | A third party reproduces the headline rung from the Docker/Zenodo bundle, offline, byte-for-byte on the frozen inputs. | external sign-off | `make replicate` / `Dockerfile` / `.zenodo.json` |

Rungs 6–9 are the **confirmation block**: a transition is "confirmed" only when
the joint confirmatory rule passes (rung 6) **and** the system is specific
(rung 7) **and** it predicts out of sample (rung 8). Rung 9 makes the whole claim
*portable* — reproducible by someone with no access to this machine.

## The rung-6 joint rule (the bar that decides "confirmed")

A real series is **CONFIRMED** only if **all** of:

- **Test A — accumulation specificity:** the localized-transition gate **rejects**
  smooth non-bifurcating accumulations (`accumulation_fpr ≤ 0.25`). Guards against
  ORI-C being merely a *trend* detector.
- **Test B — surrogate null:** observed crossing statistic beats IAAFT surrogates
  at **p < 0.01**. Guards against the series' own autocorrelation.
- **Test C — multiverse:** `ROBUST_POSITIVE` (fires in ≥ 80 % of 27 defensible
  specs). Guards against proxy cherry-picking.
- **Test D — effect vs SESOI:** the 99 % CI for the C-jump lies beyond SESOI
  (`EFFECT_EXCEEDS_SESOI`). A magnitude statement, not a transition claim on its own.

Robustness is **necessary but not sufficient**: a `ROBUST_POSITIVE` that fails
Test B is a robust *trend*, not a confirmed transition.

## Where ORI-C stands today (see `EVIDENTIARY_STATUS.md` for the live detail)

| Rung | Cleared? | Evidence |
|------|----------|----------|
| 0 Mechanism | ✅ | `oric.endogenous` saddle-node + linear twin |
| 1 Smoke | ✅ | CI `smoke_ci_accept` |
| 2 Synthetic indicative | ✅ | T1–T8 ACCEPT (indicative) |
| 3 Synthetic full-statistical | ✅ | endogenous bistable N=50, effect ≈ +1.13, CI₉₉ [0.83, 1.82], twin FPR 0.08 |
| 4 Real exploratory | ◑ | 5 ACCEPT / 2 REJECT, Level B, the one densified ACCEPT (Pantheon) is config-fragile |
| 5 Real canonical | ⬜ | no real pilot has a `full_statistical`/canonical proof run yet |
| 5–6 Registered A/B/C block | ❌ | frozen FRED block → **`REAL_BLOCK_REJECTED`**: ORI-C silent on A (crossing 0.0, surrogate p=1.0) — but **specific** (silent on B/C while the classical panel false-fires 8×). Artifact stored: `05_Results/registered_block/` (contract `contracts/REAL_DATA_REGISTRATION.json`) |
| 6 Confirmed transition | ❌ | both headline ACCEPTs are **NOT_CONFIRMED** (Test B fails: Pantheon p≈0.17, FRED p=1.0) |
| 7 Strong-negatives clean | ✅ | **`STRONG_NEGATIVES_CLEAN`** stored (`05_Results/strong_negatives/`): the localized gate fires on 0/11 adversarial negatives (FPR 0.0 ≤ 0.10) with bifurcation TPR 1.0 ≥ 0.50; the legacy bare-ΔC gate leaks on 54.5 % and is kept visible as `raw_detector_fired` for audit |
| 8 OOS pre-registered | ◑ | confirmatory run under the frozen protocol (`lead=60`, N=50) stored (`05_Results/oos_prediction/`): TPR 0.14 / twin FPR 0.04, Fisher p≈0.08 → **`OOS_SKILL_INCONCLUSIVE`** (honest negative); FRED forward prediction (Part B) still registered-pending |
| 9 External replication | ⬜ | Docker/Zenodo bundle prepared; no third-party sign-off yet |

**One line:** ORI-C is a *built, falsifiable test machine* that has cleared the
**synthetic mechanism** rungs (0–3) but is **NOT_CONFIRMED** on real data — it sits
below rung 6 because the surrogate-null gate (Test B) fails. That is an honest
negative, reported at equal status to a positive.

## Why an integrator makes the high rungs hard (and why that is the point)

Because `C(t+1) = C(t) + β·S − γ·V` is an **integrator**, any monotone driver
makes `C` grow and "look self-reinforcing". So the trivial rival hypothesis —
"ORI-C is a trend detector" — passes rungs 1–4 for free. Rungs 6–8 exist
*specifically* to kill that rival: Test A (specificity to localized change),
the strong-negatives battery (rung 7), and a pre-registered OOS prediction of a
*localized regime change* rather than "C keeps rising" (rung 8). Clearing them is
what would separate a genuine phase transition from an accumulating trend.
