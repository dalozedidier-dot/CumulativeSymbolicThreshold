"""Unit tests for run_oos_panel.py.

Tests cover:
  - _cap_formula / _compute_cap: formula selection based on calibration coverage
  - _detect_threshold_cal_params: normal, constant, too-few-points edge cases
  - _threshold_hit_test: strict hit, exceed_frac, NaN threshold
  - _evaluate_geo: integration check on a synthetic geo DataFrame
  - _aggregate: verdict logic
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure pipeline package is on sys.path
_CODE = Path(__file__).resolve().parents[1]
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from pipeline.run_oos_panel import (
    _cap_formula,
    _compute_cap,
    _detect_threshold_cal_params,
    _threshold_hit_test,
    _evaluate_geo,
    _aggregate,
)


# ── _cap_formula / _compute_cap ────────────────────────────────────────────────

def _make_geo(n: int, cols: dict[str, list | None]) -> pd.DataFrame:
    """Build a minimal geo DataFrame with given column arrays (None → all NaN)."""
    data: dict = {"geo": ["XX"] * n, "year": list(range(2000, 2000 + n))}
    for col, vals in cols.items():
        data[col] = vals if vals is not None else [float("nan")] * n
    return pd.DataFrame(data)


class TestCapFormula:
    def test_ori_when_all_covered(self):
        df = _make_geo(20, {"O": [0.5] * 20, "R": [0.6] * 20, "I": [0.7] * 20})
        assert _cap_formula(df) == "ORI"

    def test_or_when_i_sparse(self):
        # I has only 2 non-null out of 20 → coverage = 0.10 < 0.25
        i_vals = [float("nan")] * 18 + [0.5, 0.6]
        df = _make_geo(20, {"O": [0.5] * 20, "R": [0.6] * 20, "I": i_vals})
        assert _cap_formula(df) == "OR"

    def test_o_when_r_and_i_sparse(self):
        df = _make_geo(20, {"O": [0.5] * 20, "R": None, "I": None})
        assert _cap_formula(df) == "O"

    def test_none_when_no_valid_column(self):
        df = _make_geo(20, {})
        assert _cap_formula(df) == "none"

    def test_compute_cap_ori(self):
        df = _make_geo(5, {"O": [0.5] * 5, "R": [0.8] * 5, "I": [0.9] * 5})
        cap = _compute_cap(df, "ORI")
        expected = 0.5 * 0.8 * 0.9
        assert cap.notna().all()
        assert float(cap.iloc[0]) == pytest.approx(expected)

    def test_compute_cap_or(self):
        df = _make_geo(5, {"O": [0.4] * 5, "R": [0.6] * 5, "I": None})
        cap = _compute_cap(df, "OR")
        assert float(cap.iloc[0]) == pytest.approx(0.24)

    def test_compute_cap_o_only(self):
        df = _make_geo(5, {"O": [0.3] * 5})
        cap = _compute_cap(df, "O")
        assert float(cap.iloc[0]) == pytest.approx(0.3)

    def test_compute_cap_none_returns_nan(self):
        df = _make_geo(5, {})
        cap = _compute_cap(df, "none")
        assert cap.isna().all()

    def test_compute_cap_infers_formula_when_empty(self):
        """_compute_cap with empty formula string falls back to _cap_formula."""
        df = _make_geo(20, {"O": [0.5] * 20, "R": [0.6] * 20})
        cap = _compute_cap(df, "")
        assert cap.notna().all()
        assert float(cap.iloc[0]) == pytest.approx(0.3)


# ── _detect_threshold_cal_params ───────────────────────────────────────────────

class TestDetectThresholdCalParams:
    def test_normal_case(self):
        rng = np.random.default_rng(0)
        x = rng.normal(loc=0.01, scale=0.05, size=30)
        mu, sigma, thr, reliable = _detect_threshold_cal_params(x, k=2.5, m=3)
        assert reliable is True
        assert np.isfinite(mu) and np.isfinite(sigma) and np.isfinite(thr)
        assert thr == pytest.approx(mu + 2.5 * sigma, rel=1e-6)

    def test_constant_series_flagged_unreliable(self):
        x = np.full(20, 0.05)
        mu, sigma, thr, reliable = _detect_threshold_cal_params(x, k=2.5, m=3)
        assert reliable is False
        assert np.isfinite(mu)
        assert sigma < 1e-9
        # threshold falls back to mu for constant series
        assert thr == pytest.approx(mu, abs=1e-12)

    def test_too_few_points_returns_nan(self):
        x = np.array([0.1, 0.2])  # only 2 points < 3
        mu, sigma, thr, reliable = _detect_threshold_cal_params(x, k=2.5, m=3)
        assert reliable is False
        assert not np.isfinite(mu)
        assert not np.isfinite(thr)

    def test_nan_values_ignored(self):
        x = np.array([float("nan"), 0.01, 0.02, float("nan"), 0.03])
        mu, sigma, thr, reliable = _detect_threshold_cal_params(x, k=2.5, m=3)
        # 3 finite values: should succeed
        assert np.isfinite(mu)


# ── _threshold_hit_test ────────────────────────────────────────────────────────

class TestThresholdHitTest:
    def test_m_consecutive_gives_strict_hit(self):
        thr = 0.05
        delta = np.array([0.0, 0.1, 0.1, 0.1, 0.0])  # 3 consecutive > 0.05
        hit, frac, consec = _threshold_hit_test(delta, thr, m=3)
        assert hit is True
        assert frac == pytest.approx(3 / 5)
        assert consec == 3

    def test_two_consecutive_no_strict_hit_with_m3(self):
        thr = 0.05
        delta = np.array([0.1, 0.1, 0.0, 0.1, 0.0])  # max run = 2
        hit, frac, consec = _threshold_hit_test(delta, thr, m=3)
        assert hit is False
        assert consec == 2

    def test_nan_threshold_returns_nan_frac(self):
        delta = np.array([0.1, 0.2, 0.3])
        hit, frac, consec = _threshold_hit_test(delta, float("nan"), m=3)
        assert hit is False
        assert not np.isfinite(frac)
        assert consec == 0

    def test_all_nan_test_returns_nan_frac(self):
        delta = np.full(5, float("nan"))
        hit, frac, consec = _threshold_hit_test(delta, 0.05, 3)
        assert hit is False
        assert not np.isfinite(frac)

    def test_zero_exceedances(self):
        thr = 1.0
        delta = np.array([0.1, 0.2, 0.3])
        hit, frac, consec = _threshold_hit_test(delta, thr, m=2)
        assert hit is False
        assert frac == pytest.approx(0.0)
        assert consec == 0


# ── _evaluate_geo ──────────────────────────────────────────────────────────────

class TestEvaluateGeo:
    def _make_increasing_series(self) -> pd.DataFrame:
        """Geo with clean upward trend in O and R — should produce reliable threshold."""
        n = 40
        years = list(range(1990, 1990 + n))
        O = [0.3 + 0.01 * i for i in range(n)]
        R = [0.5 + 0.005 * i for i in range(n)]
        return pd.DataFrame({"geo": ["XX"] * n, "year": years, "O": O, "R": R})

    def test_basic_eval_returns_ok(self):
        df = self._make_increasing_series()
        res = _evaluate_geo(df, outcome_col="O", split_year=2015, k=2.5, m=3)
        assert res["result"] == "OK"
        assert res["n_cal"] > 0
        assert res["n_test"] > 0

    def test_skip_if_too_few_cal_points(self):
        # years 2013, 2014 ≤ split_year=2014 → n_cal=2 < 3 → SKIP
        n = 4
        df = pd.DataFrame({
            "geo": ["ZZ"] * n,
            "year": [2013, 2014, 2015, 2016],
            "O": [0.5] * n,
        })
        res = _evaluate_geo(df, outcome_col="O", split_year=2014, k=2.5, m=3)
        assert res["result"] == "SKIP"

    def test_cap_formula_stored_in_result(self):
        df = self._make_increasing_series()
        res = _evaluate_geo(df, outcome_col="O", split_year=2015, k=2.5, m=3)
        assert "cap_formula" in res
        assert res["cap_formula"] in ("ORI", "OR", "O", "none")

    def test_threshold_exceed_frac_is_finite_when_data_ok(self):
        """With a clear trend in O*R calibration, threshold should be computable."""
        df = self._make_increasing_series()
        res = _evaluate_geo(df, outcome_col="O", split_year=2015, k=2.5, m=3)
        # With a smooth increasing series, delta_Cap should be nearly constant
        # (reliable=False) OR positive (reliable=True). Either way, exceed_frac
        # should be a valid float (not NaN) because threshold = mu (fallback).
        assert np.isfinite(res["threshold_exceed_frac_post"]) or res["n_test"] == 0


# ── _aggregate ─────────────────────────────────────────────────────────────────

class TestAggregate:
    def _geo_result(
        self,
        corr: float,
        exceed: float,
        naive_rmse: float = 0.2,
        oos_rmse: float = 0.1,
    ) -> dict:
        return {
            "geo": "XX",
            "n_cal": 10,
            "n_test": 5,
            "oos_corr": corr,
            "oos_vs_naive": "better" if oos_rmse < naive_rmse else "worse_or_equal",
            "naive_rmse": naive_rmse,
            "oos_rmse": oos_rmse,
            "threshold_exceed_frac_post": exceed,
            "threshold_hit_oos": False,
            "result": "OK",
        }

    def test_accept_when_majority_better_and_corr_and_exceed(self):
        per_geo = [
            self._geo_result(0.8, 0.30),   # better, high exceed
            self._geo_result(0.7, 0.10),   # better, low exceed
            self._geo_result(-0.3, 0.05, oos_rmse=0.3),  # worse
        ]
        agg = _aggregate(per_geo, alpha=0.01)
        assert agg["verdict"] == "ACCEPT"

    def test_reject_when_majority_corr_negative(self):
        per_geo = [
            self._geo_result(-0.5, 0.0, oos_rmse=0.3),
            self._geo_result(-0.4, 0.0, oos_rmse=0.35),
            self._geo_result(0.1, 0.0),
        ]
        agg = _aggregate(per_geo, alpha=0.01)
        assert agg["verdict"] == "REJECT"

    def test_indeterminate_when_exceed_below_threshold(self):
        per_geo = [
            self._geo_result(0.8, 0.05),   # better corr, but exceed < 0.25
            self._geo_result(0.6, 0.10),
            self._geo_result(-0.1, 0.0, oos_rmse=0.25),
        ]
        agg = _aggregate(per_geo, alpha=0.01)
        assert agg["verdict"] == "INDETERMINATE"

    def test_insufficient_data_not_counted_as_worse(self):
        per_geo = [
            {**self._geo_result(float("nan"), float("nan")),
             "oos_vs_naive": "insufficient_data", "oos_corr": float("nan"),
             "n_test": 0},
            self._geo_result(0.8, 0.30),
            self._geo_result(0.7, 0.10),
        ]
        agg = _aggregate(per_geo, alpha=0.01)
        # "insufficient_data" must not count against majority — two "better" geos
        # should dominate
        assert agg["verdict"] in ("ACCEPT", "INDETERMINATE")
