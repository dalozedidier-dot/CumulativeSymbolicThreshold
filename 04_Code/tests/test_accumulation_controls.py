"""Tests for oric.accumulation_controls — the decisive trend-vs-transition controls."""
from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

from oric.accumulation_controls import (
    BIFURCATING,
    NON_BIFURCATING,
    accumulation_control_catalogue,
    exponential_saturation,
    gen_accumulation,
    gompertz,
    linear_ramp,
    logistic_growth,
    run_accumulation_control_suite,
)


def test_pure_curves_are_monotone_nondecreasing():
    t = np.arange(200, dtype=float)
    curves = [
        logistic_growth(t, 0.5, 1.5, midpoint=100, rate=0.05),
        gompertz(t, 0.5, 1.5, b=float(np.exp(4.0)), c=8.0 / 200),
        exponential_saturation(t, 0.5, 1.5, rate=4.0 / 200),
        linear_ramp(t, 0.5, 1.5),
    ]
    for c in curves:
        assert np.all(np.diff(c) >= -1e-9), "smooth accumulation curves must be non-decreasing"
        assert c[-1] > c[0]


def test_non_bifurcating_demand_is_trending_and_smooth():
    n = 220
    for kind in NON_BIFURCATING:
        df = gen_accumulation(kind, n, seed=5)
        d = df["demand"].to_numpy()
        rho, _ = spearmanr(np.arange(n), d)
        assert rho > 0.85, f"{kind}: demand should be a strong monotone trend (rho={rho:.2f})"


def test_bifurcation_has_more_localized_jump_than_smooth_accumulation():
    n = 220
    # Largest single-step increment, normalized by total range, is the
    # localization signature: a genuine break concentrates change in few steps.
    def max_step_frac(kind: str) -> float:
        d = gen_accumulation(kind, n, seed=5)["demand"].to_numpy()
        rng = d.max() - d.min()
        return float(np.max(np.abs(np.diff(d))) / (rng + 1e-9))

    sharp = max_step_frac("sharp_regime_switch")
    smooth = max(max_step_frac(k) for k in ("logistic_growth", "gompertz", "linear_ramp"))
    assert sharp > smooth, f"bifurcation jump ({sharp:.3f}) should exceed smoothest accumulation ({smooth:.3f})"


def test_catalogue_structure():
    cat = accumulation_control_catalogue(n=120, seed=1)
    assert len(cat) == len(NON_BIFURCATING) + len(BIFURCATING)
    negs = [e for e in cat if e.label == 0]
    poss = [e for e in cat if e.label == 1]
    assert len(negs) == len(NON_BIFURCATING)
    assert len(poss) == len(BIFURCATING)
    assert all(e.is_non_bifurcating for e in negs)
    for e in cat:
        assert {"t", "O", "R", "I", "demand"}.issubset(e.df.columns)


def test_suite_runs_and_reports_decisive_metrics():
    res = run_accumulation_control_suite(n=140, seed=1234, n_surrogates=0)
    assert res["schema"] == "oric.accumulation_control.v1"
    assert len(res["outcomes"]) == len(NON_BIFURCATING) + len(BIFURCATING)
    assert 0.0 <= res["accumulation_fpr"] <= 1.0
    assert 0.0 <= res["bifurcation_tpr"] <= 1.0
    assert isinstance(res["separates"], bool)
    # Every outcome carries the bare-detector firing decision.
    for o in res["outcomes"]:
        assert isinstance(o["detector_fired"], bool)
        assert o["max_run"] >= 0


def test_suite_with_surrogates_attaches_pvalues():
    res = run_accumulation_control_suite(n=120, seed=7, n_surrogates=20)
    for o in res["outcomes"]:
        assert o["surrogate_p_rate"] is None or 0.0 < o["surrogate_p_rate"] <= 1.0
        assert o["surrogate_p_maxrun"] is None or 0.0 < o["surrogate_p_maxrun"] <= 1.0


def test_localized_gate_separates_accumulation_from_bifurcation():
    res = run_accumulation_control_suite(n=220, seed=1234, n_surrogates=0)
    assert res["raw_accumulation_fpr"] == 1.0
    assert res["accumulation_fpr"] <= 0.25
    assert res["bifurcation_tpr"] == 1.0
    assert res["separates"] is True


def test_localized_gate_records_audit_metrics():
    res = run_accumulation_control_suite(n=160, seed=11, n_surrogates=0)
    for outcome in res["outcomes"]:
        assert "raw_detector_fired" in outcome
        assert "acceleration_concentration" in outcome
        assert "acceleration_peak_fraction" in outcome
        assert 0.0 <= outcome["acceleration_concentration"] <= 1.0
        assert 0.0 <= outcome["acceleration_peak_fraction"] <= 1.0
