"""Tests for oric.effect_size — effect size vs SESOI + achieved power."""
from __future__ import annotations

import numpy as np

from oric.effect_size import cohens_d, hedges_g, achieved_power, effect_size_report


def test_cohens_d_recovers_known_shift():
    rng = np.random.default_rng(0)
    pre = rng.normal(0.0, 1.0, 5000)
    post = rng.normal(1.0, 1.0, 5000)
    d = cohens_d(pre, post)
    assert 0.9 < d < 1.1  # ~1 SD separation


def test_hedges_g_is_bias_corrected_smaller_than_d():
    rng = np.random.default_rng(1)
    pre = rng.normal(0.0, 1.0, 12)
    post = rng.normal(1.0, 1.0, 12)
    assert abs(hedges_g(pre, post)) < abs(cohens_d(pre, post))


def test_achieved_power_in_unit_range_and_monotone_in_n():
    p_small = achieved_power(0.3, 20, 20, alpha=0.01)
    p_large = achieved_power(0.3, 1000, 1000, alpha=0.01)
    assert 0.0 <= p_small <= 1.0
    assert 0.0 <= p_large <= 1.0
    assert p_large > p_small
    assert achieved_power(0.0, 50, 50) < 0.2  # no effect → ~alpha-level power


def test_report_underpowered_small_n_inconclusive():
    # Small n, modest effect → 99% CI straddles the SESOI and power is low.
    rng = np.random.default_rng(2)
    rep = effect_size_report(rng.normal(0, 1, 18), rng.normal(0.25, 1, 18),
                             rng=np.random.default_rng(3))
    assert rep.verdict == "UNDERPOWERED"
    assert rep.achieved_power_at_sesoi < rep.power_gate


def test_large_effect_small_n_ci_overrides_power_gate():
    # A huge effect whose 99% CI clears the SESOI is confirmed even when the
    # design is underpowered for the SESOI (direct CI evidence is power-independent).
    rng = np.random.default_rng(20)
    rep = effect_size_report(rng.normal(0, 1, 60), rng.normal(2.0, 1, 60),
                             rng=np.random.default_rng(21))
    assert rep.achieved_power_at_sesoi < rep.power_gate    # underpowered for the SESOI
    assert min(abs(rep.ci_low), abs(rep.ci_high)) >= rep.sesoi_robust_sd
    assert rep.verdict == "EFFECT_EXCEEDS_SESOI"


def test_report_effect_exceeds_sesoi_when_large_and_powered():
    rng = np.random.default_rng(4)
    rep = effect_size_report(rng.normal(0, 1, 500), rng.normal(0.7, 1, 500),
                             rng=np.random.default_rng(5))
    assert rep.achieved_power_at_sesoi >= rep.power_gate  # well powered
    assert rep.verdict == "EFFECT_EXCEEDS_SESOI"
    assert min(abs(rep.ci_low), abs(rep.ci_high)) >= rep.sesoi_robust_sd


def test_report_effect_below_sesoi_when_null_and_powered():
    rng = np.random.default_rng(6)
    rep = effect_size_report(rng.normal(0, 1, 500), rng.normal(0.0, 1, 500),
                             rng=np.random.default_rng(7))
    assert rep.achieved_power_at_sesoi >= rep.power_gate
    assert rep.verdict == "EFFECT_BELOW_SESOI"


def test_decision_never_uses_pvalue():
    # The reporting rule forbids a p-value driving the real-data decision.
    rng = np.random.default_rng(8)
    rep = effect_size_report(rng.normal(0, 1, 100), rng.normal(0.3, 1, 100))
    assert "p_value" not in rep.to_dict()
    assert "p" not in rep.to_dict()
