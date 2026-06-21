"""Tests for oric.surrogates — IAAFT surrogates and the threshold-crossing null."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from oric.surrogates import (
    iaaft_surrogate,
    iaaft_surrogates,
    threshold_crossing_statistic,
    surrogate_null_test,
)
from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations


def _signal(n=256, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    # autocorrelated + trend + non-Gaussian marginal
    x = np.cumsum(rng.normal(0, 1, n)) * 0.1 + np.sin(2 * np.pi * t / 40) + rng.gamma(2.0, 1.0, n)
    return x


def test_iaaft_preserves_amplitude_distribution_exactly():
    x = _signal()
    s = iaaft_surrogate(x, n_iter=100, rng=np.random.default_rng(1))
    # IAAFT rank-matches to the original samples → identical multiset of values.
    np.testing.assert_allclose(np.sort(s), np.sort(x), rtol=0, atol=1e-9)


def test_iaaft_preserves_power_spectrum_closely():
    x = _signal()
    s = iaaft_surrogate(x, n_iter=200, rng=np.random.default_rng(2))
    ax = np.abs(np.fft.rfft(x - x.mean()))
    asur = np.abs(np.fft.rfft(s - s.mean()))
    # Spectra should be highly correlated (IAAFT enforces the amplitude spectrum).
    corr = np.corrcoef(ax, asur)[0, 1]
    assert corr > 0.95, f"spectral correlation too low: {corr}"


def test_iaaft_is_a_permutation_not_identity():
    x = _signal()
    s = iaaft_surrogate(x, n_iter=100, rng=np.random.default_rng(3))
    # Same values, but reordered (phase destroyed) → not the original ordering.
    assert not np.allclose(s, x)


def test_iaaft_reproducible_with_seed():
    x = _signal()
    s1 = iaaft_surrogate(x, n_iter=50, rng=np.random.default_rng(7))
    s2 = iaaft_surrogate(x, n_iter=50, rng=np.random.default_rng(7))
    np.testing.assert_array_equal(s1, s2)


def test_iaaft_short_or_constant_series_safe():
    assert iaaft_surrogate(np.array([1.0, 2.0])).size == 2          # too short → returned as-is
    const = np.full(50, 3.0)
    np.testing.assert_array_equal(iaaft_surrogate(const), const)     # constant → unchanged


def test_iaaft_surrogates_count():
    x = _signal()
    surs = iaaft_surrogates(x, 5, rng=np.random.default_rng(0))
    assert len(surs) == 5
    assert all(s.size == x.size for s in surs)


def test_threshold_crossing_statistic_counts_and_runs():
    # baseline (first 5) ~0; then a sustained block of high values.
    delta = np.array([0.0, 0.1, -0.1, 0.0, 0.05] + [5.0] * 4 + [0.0] * 3)
    cs = threshold_crossing_statistic(delta, k=2.5, m=3, baseline_n=5)
    assert cs.n_crossings == 4
    assert cs.max_run == 4
    assert cs.sustained_hit is True
    assert 0.0 < cs.crossing_rate <= 1.0


def test_threshold_crossing_no_sustained_when_isolated():
    delta = np.array([0.0, 0.1, -0.1, 0.0, 0.05] + [5.0, 0.0, 5.0, 0.0, 5.0])
    cs = threshold_crossing_statistic(delta, k=2.5, m=3, baseline_n=5)
    assert cs.max_run == 1
    assert cs.sustained_hit is False


def test_surrogate_null_test_end_to_end():
    rng = np.random.default_rng(11)
    n = 160
    df = pd.DataFrame({
        "t": np.arange(n),
        "O": np.clip(0.6 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "R": np.clip(0.65 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "I": np.clip(0.58 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "demand": np.linspace(0.6, 1.5, n) * (1 + rng.normal(0, 0.02, n)),
    })
    cfg = ORICConfig(seed=11, n_steps=n, intervention="none")
    res = surrogate_null_test(
        df, cfg, n_surrogates=30, statistic="crossing_rate",
        rng=np.random.default_rng(0), run_fn=run_oric_from_observations,
    )
    assert 0.0 < res.p_value <= 1.0
    assert res.n_surrogates == 30
    assert set(res.surrogate_columns) == {"O", "R", "I", "demand"}
    assert "crossing_rate" in res.observed_crossing  # full CrossingStatistic dict
    assert isinstance(res.significant_at_01, bool)


def test_surrogate_null_rejects_unknown_columns():
    df = pd.DataFrame({"t": np.arange(10), "X": np.arange(10.0)})
    cfg = ORICConfig(seed=1, n_steps=10)
    with pytest.raises(ValueError):
        surrogate_null_test(df, cfg, n_surrogates=2, surrogate_columns=("O", "R"),
                            run_fn=run_oric_from_observations)
