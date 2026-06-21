"""confirmatory.py — Joint confirmatory verdict over the decisive controls.

Confirmation of a *genuine phase transition* (as opposed to a detectable trend)
requires several controls to pass **jointly**. Any single one is necessary but
not sufficient:

  Test A (global, detector property) — smooth-accumulation specificity:
      the bare ΔC criterion must NOT fire on smooth non-bifurcating accumulations
      (accumulation_fpr ≤ 0.25).  [oric.accumulation_controls]
  Test B (per series) — IAAFT surrogate null:
      the observed crossing statistic must beat the spectral null (p < 0.01).
      [oric.surrogates]
  Test C (per series) — specification curve / multiverse:
      the verdict must survive defensible analytic choices (ROBUST_POSITIVE).
      [oric.multiverse]
  Test D (per series) — effect size vs SESOI + power:
      the C effect must exceed the SESOI with adequate evidence.
      [oric.effect_size]

A series is CONFIRMED only if A (global) passes AND B, C, D (this series) pass.
This operationalises the honest reporting rule: most current pilots are *not*
confirmed because Test A (a property of the detector itself) currently fails.
"""
from __future__ import annotations

import numpy as np


def run_confirmatory_suite(
    df_obs,
    cfg,
    *,
    n_surrogates: int = 200,
    multiverse_specs=None,
    accumulation_n: int = 220,
    accumulation_seed: int = 1234,
    rng: np.random.Generator | None = None,
    run_fn=None,
) -> dict:
    """Run Tests A–D and return a joint confirmatory verdict for one series.

    Test A is a global property of the detector (independent of this series); it
    is computed once here so the combined verdict reflects the full rule.
    """
    from oric.surrogates import surrogate_null_test
    from oric.multiverse import run_multiverse
    from oric.effect_size import effect_size_report
    from oric.accumulation_controls import run_accumulation_control_suite
    from oric.frozen_params import FROZEN_PARAMS

    if run_fn is None:
        try:
            from pipeline.ori_c_pipeline import run_oric_from_observations, _detect_threshold  # type: ignore
        except ModuleNotFoundError:  # pragma: no cover - layout-dependent
            from ori_c_pipeline import run_oric_from_observations, _detect_threshold  # type: ignore
        run_fn = run_oric_from_observations
    else:  # threshold detector for pre/post split
        try:
            from pipeline.ori_c_pipeline import _detect_threshold  # type: ignore
        except ModuleNotFoundError:  # pragma: no cover
            from ori_c_pipeline import _detect_threshold  # type: ignore

    rng = np.random.default_rng() if rng is None else rng

    # ── Test A — global detector specificity ────────────────────────────────
    acc = run_accumulation_control_suite(n=accumulation_n, seed=accumulation_seed, n_surrogates=0)
    test_a_pass = acc["accumulation_fpr"] <= 0.25

    # ── Test B — surrogate null on this series ──────────────────────────────
    res_b = surrogate_null_test(df_obs, cfg, n_surrogates=n_surrogates,
                                statistic="crossing_rate", rng=rng, run_fn=run_fn)
    test_b_pass = bool(res_b.significant_at_01)

    # ── Test C — multiverse on this series ──────────────────────────────────
    res_c = run_multiverse(df_obs, cfg, specs=multiverse_specs, run_fn=run_fn)
    test_c_pass = res_c["robustness"] == "ROBUST_POSITIVE"

    # ── Test D — effect size vs SESOI on this series ────────────────────────
    run = run_fn(df_obs, cfg)
    C = run["C"].to_numpy()
    if "delta_C" not in run.columns:
        run = run.copy()
        run["delta_C"] = run["C"].diff().fillna(0.0)
    thr_idx, _ = _detect_threshold(run["delta_C"], cfg.k, cfg.m, cfg.baseline_n)
    n = C.size
    win = max(int(getattr(cfg, "baseline_n", 30)), n // 4)
    if thr_idx is not None and 0 < thr_idx < n:
        pre, post = C[max(0, thr_idx - win):thr_idx], C[thr_idx:min(n, thr_idx + win)]
    else:
        cut = int(0.40 * n)
        pre, post = C[:cut], C[n - cut:]
    res_d = effect_size_report(
        pre, post, sesoi_robust_sd=FROZEN_PARAMS.sesoi_c_robust_sd,
        alpha=FROZEN_PARAMS.alpha, ci_level=FROZEN_PARAMS.ci_level,
        power_gate=FROZEN_PARAMS.power_gate_min, rng=rng,
    )
    test_d_pass = res_d.verdict == "EFFECT_EXCEEDS_SESOI"

    tests = {
        "A_accumulation_specificity": {
            "pass": bool(test_a_pass), "accumulation_fpr": acc["accumulation_fpr"],
            "scope": "global_detector_property",
        },
        "B_surrogate_null": {
            "pass": test_b_pass, "p_value": res_b.p_value, "observed": res_b.observed,
            "null_q99": res_b.null_q99,
        },
        "C_multiverse": {
            "pass": test_c_pass, "robustness": res_c["robustness"],
            "fired_fraction": res_c["fired_fraction"],
        },
        "D_effect_size": {
            "pass": test_d_pass, "verdict": res_d.verdict,
            "standardised_effect": res_d.standardised_effect,
            "ci": [res_d.ci_low, res_d.ci_high],
            "power_at_sesoi": res_d.achieved_power_at_sesoi,
        },
    }
    confirmed = all(t["pass"] for t in tests.values())
    failing = [name for name, t in tests.items() if not t["pass"]]

    return {
        "schema": "oric.confirmatory.v1",
        "confirmed": bool(confirmed),
        "verdict": "CONFIRMED" if confirmed else "NOT_CONFIRMED",
        "failing_tests": failing,
        "limiting_factor": (failing[0] if failing else None),
        "tests": tests,
        "joint_rule": "CONFIRMED iff A(global) AND B AND C AND D all pass.",
    }
