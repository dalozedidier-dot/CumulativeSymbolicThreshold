"""test_early_warning.py — Critical-slowing-down detector + harder nulls (axes 2, 5).

Validates that CSD (rising AR(1) + variance) separates a genuine fold approach
from smooth trends, and that the trend-preserving surrogate null isolates the
localized transition from a mere trend (correct false-positive control).
"""
from __future__ import annotations

import numpy as np
import pytest

from oric.early_warning import (
    composite_csd_statistic,
    csd_surrogate_test,
    early_warning,
    early_warning_before_jump,
    find_jump,
    gaussian_detrend,
    kendall_trend,
    rolling_autocorr1,
    rolling_variance,
)
from oric.endogenous import EndogenousConfig, matched_fold_pair
from oric.surrogates import series_surrogate_test, trend_preserving_surrogate


# --- helpers ---------------------------------------------------------------

def _trend_plus_ar1(n, slope, phi, sd, rng):
    e = rng.standard_normal(n) * sd
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = phi * y[i - 1] + e[i]
    return slope * np.linspace(0, 1, n) + y


def _explicit_slowing_down(n, rng):
    """AR(1) with φ ramping 0.1→0.97 (genuine critical slowing down: AR(1) and
    variance both rise) on top of a linear trend."""
    phi = np.linspace(0.1, 0.97, n)
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = phi[i] * y[i - 1] + 0.1 * rng.standard_normal()
    return 0.5 * np.linspace(0, 1, n) + y


# --- indicators ------------------------------------------------------------

class TestIndicators:
    def test_gaussian_detrend_removes_linear_trend(self):
        x = 3.0 * np.linspace(0, 1, 500) + 0.01 * np.random.default_rng(0).standard_normal(500)
        resid = gaussian_detrend(x, bandwidth=40.0)
        # Residual mean ~0 and far smaller spread than the original trend range.
        assert abs(float(np.mean(resid))) < 0.05
        assert np.ptp(resid) < 0.5 * np.ptp(x)

    def test_rolling_variance_matches_reference(self):
        x = np.random.default_rng(1).standard_normal(200)
        rv = rolling_variance(x, 50)
        assert rv.size == 200 - 50 + 1
        assert rv[0] == pytest.approx(float(np.var(x[:50])))
        assert rv[-1] == pytest.approx(float(np.var(x[-50:])))

    def test_rolling_autocorr1_detects_persistence(self):
        rng = np.random.default_rng(2)
        white = rng.standard_normal(400)
        ar1 = _trend_plus_ar1(400, 0.0, 0.8, 1.0, rng)
        ac_white = float(np.mean(rolling_autocorr1(white, 80)))
        ac_ar1 = float(np.mean(rolling_autocorr1(ar1, 80)))
        assert ac_ar1 > ac_white + 0.3

    def test_kendall_trend_degenerate(self):
        assert kendall_trend(np.zeros(10)) == (0.0, 1.0)
        assert kendall_trend(np.array([1.0])) == (0.0, 1.0)
        tau, _ = kendall_trend(np.arange(20.0))
        assert tau == pytest.approx(1.0)


# --- detector discrimination ----------------------------------------------

class TestEarlyWarning:
    def test_statistic_higher_for_slowing_down_than_noise(self):
        rng = np.random.default_rng(3)
        csd = _explicit_slowing_down(1200, rng)
        noise = rng.standard_normal(1200)
        s_csd = early_warning(csd, window=300, bandwidth=90.0).composite_tau
        s_noise = early_warning(noise, window=300, bandwidth=90.0).composite_tau
        assert s_csd > 0.1
        assert s_csd > s_noise

    def test_short_series_safe(self):
        ew = early_warning(np.arange(5.0))
        assert ew.n == 5 and ew.composite_tau == 0.0

    def test_find_jump_and_before_jump(self):
        x = np.concatenate([np.zeros(100), np.ones(100)])
        assert find_jump(x) == 100
        # before-jump segment excludes the step, so the result is well-defined
        res = early_warning_before_jump(x, window=20, bandwidth=10.0)
        assert res.n <= 100


# --- harder nulls (axis 5) -------------------------------------------------

class TestTrendPreservingSurrogate:
    def test_preserves_trend_scrambles_residual(self):
        rng = np.random.default_rng(5)
        x = 2.0 * np.linspace(0, 1, 600) + 0.1 * rng.standard_normal(600)
        surr = trend_preserving_surrogate(x, bandwidth=50.0, rng=rng)
        from scipy.ndimage import gaussian_filter1d
        tx = gaussian_filter1d(x, 50.0, mode="reflect")
        ts = gaussian_filter1d(surr, 50.0, mode="reflect")
        # Trend preserved (smoothed curves nearly identical) ...
        assert np.corrcoef(tx, ts)[0, 1] > 0.99
        # ... and the residual amplitude distribution is preserved exactly (IAAFT).
        assert np.allclose(np.sort(x - tx), np.sort(surr - tx), atol=1e-6) or \
            np.corrcoef(np.sort(x - tx), np.sort(surr - tx))[0, 1] > 0.999

    def test_series_surrogate_test_flags_localized_burst(self):
        x = _explicit_slowing_down(1000, np.random.default_rng(6))
        res = series_surrogate_test(
            x, lambda s: composite_csd_statistic(s, window=250, bandwidth=70.0),
            surrogate="trend_preserving", n_surrogates=100,
            rng=np.random.default_rng(7), bandwidth=70.0,
        )
        assert res.significant_at_05
        assert res.observed > res.null_mean


class TestCSDSurrogateTest:
    def test_calibrated_on_clean_trend_null(self):
        # A pure trend + AR(1) null is not flagged at a fixed, reproducible seed.
        x = _trend_plus_ar1(1200, 0.4, 0.5, 0.05, np.random.default_rng(8))
        res = csd_surrogate_test(x, n_surrogates=100, rng=np.random.default_rng(9))
        assert not res.significant_at_05

    def test_surrogate_kinds_and_errors(self):
        x = _trend_plus_ar1(300, 0.3, 0.4, 0.1, np.random.default_rng(10))
        stat = lambda s: composite_csd_statistic(s, window=70, bandwidth=25.0)
        # iaaft kind, trend_preserving kind, and a custom callable all run.
        for kind in ("iaaft", "trend_preserving"):
            r = series_surrogate_test(x, stat, surrogate=kind, n_surrogates=20,
                                      rng=np.random.default_rng(0))
            assert 0.0 < r.p_value <= 1.0 and r.surrogate_kind == kind
        r_cb = series_surrogate_test(
            x, stat, surrogate=lambda a, rng: rng.permutation(a),
            n_surrogates=20, rng=np.random.default_rng(0))
        assert 0.0 < r_cb.p_value <= 1.0
        with pytest.raises(ValueError):
            series_surrogate_test(x, stat, surrogate="nope", n_surrogates=5,
                                  rng=np.random.default_rng(0))

    def test_result_to_dict_and_edge_cases(self):
        ew = early_warning(_trend_plus_ar1(400, 0.2, 0.3, 0.1, np.random.default_rng(0)),
                           window=100, bandwidth=30.0)
        d = ew.to_dict()
        assert {"tau_ar1", "tau_var", "composite_tau", "window"} <= set(d)
        # defensive edge cases
        assert gaussian_detrend(np.array([]), 5.0).size == 0
        assert rolling_variance(np.arange(3.0), 10).size == 0
        assert rolling_autocorr1(np.arange(3.0), 10).size == 0
        assert find_jump(np.array([1.0])) == 0

    def test_bistable_population_exceeds_twin(self):
        # Population-level: the bistable fold approach shows more CSD than its
        # matched linear twin (per-trajectory CSD is noisy; the population is clear).
        cfg = EndogenousConfig(noise_sd=0.06)
        tb, tt = [], []
        for seed in range(8):
            db, dt = matched_fold_pair(cfg, n=1200, cross=False, seed=seed)
            tb.append(composite_csd_statistic(db["C"].to_numpy(), window=300, bandwidth=85.0))
            tt.append(composite_csd_statistic(dt["C"].to_numpy(), window=300, bandwidth=85.0))
        assert np.mean(tb) > np.mean(tt) + 0.1
