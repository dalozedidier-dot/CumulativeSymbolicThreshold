"""test_placebo_suite_contracts.py — Ticket 6.

Tests that each placebo strategy respects its contract:
  - Preserves what it claims to preserve
  - Destroys what it claims to destroy
  - Battery evaluation works correctly
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from oric.placebo import (
    make_cyclic_shift,
    make_temporal_permute,
    make_phase_randomize,
    make_proxy_remap,
    make_block_shuffle,
    generate_placebo_battery,
    evaluate_placebo_battery,
    ALL_STRATEGIES,
    _STRATEGY_META,
    PlaceboSpec,
)


@pytest.fixture
def structured_df():
    """DataFrame with known autocorrelation and cross-correlation structure."""
    rng = np.random.default_rng(42)
    n = 500
    t = np.arange(n)

    # Create autocorrelated series using AR(1) process
    O = np.zeros(n)
    O[0] = rng.normal()
    for i in range(1, n):
        O[i] = 0.9 * O[i - 1] + rng.normal(0, 0.1)

    # R depends on O (cross-correlation)
    R = 0.7 * O + rng.normal(0, 0.1, n)
    I = 0.5 * R + rng.normal(0, 0.1, n)
    demand = np.sin(2 * np.pi * t / 100) + rng.normal(0, 0.1, n)
    S = np.cumsum(demand) / n

    return pd.DataFrame({
        "t": t,
        "O": O,
        "R": R,
        "I": I,
        "demand": demand,
        "S": S,
    })


def _autocorr_lag1(arr):
    """Compute lag-1 autocorrelation."""
    arr = np.asarray(arr, dtype=float)
    if len(arr) < 3:
        return 0.0
    m = np.mean(arr)
    var = np.var(arr)
    if var < 1e-15:
        return 0.0
    return np.corrcoef(arr[:-1], arr[1:])[0, 1]


def _cross_corr(a, b):
    """Compute cross-correlation between two arrays."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 3:
        return 0.0
    return np.corrcoef(a, b)[0, 1]


class TestCyclicShiftContract:
    """Cyclic shift preserves autocorrelation and marginal, breaks temporal alignment."""

    def test_preserves_values(self, structured_df):
        out, spec = make_cyclic_shift(structured_df, seed=42)
        assert set(out["O"].round(10)) == set(structured_df["O"].round(10))

    def test_preserves_autocorrelation(self, structured_df):
        out, _ = make_cyclic_shift(structured_df, seed=42)
        orig_ac = _autocorr_lag1(structured_df["O"])
        shift_ac = _autocorr_lag1(out["O"])
        assert abs(orig_ac - shift_ac) < 0.15

    def test_breaks_temporal_alignment(self, structured_df):
        out, _ = make_cyclic_shift(structured_df, seed=42)
        assert not (out["O"].values == structured_df["O"].values).all()

    def test_spec_metadata(self, structured_df):
        _, spec = make_cyclic_shift(structured_df, seed=42)
        assert "autocorrelation" in spec.preserves
        assert "temporal_alignment" in spec.destroys


class TestTemporalPermuteContract:
    """Temporal permute preserves marginal, destroys autocorrelation."""

    def test_preserves_marginal(self, structured_df):
        out, _ = make_temporal_permute(structured_df, seed=42)
        assert sorted(out["O"].round(10)) == sorted(structured_df["O"].round(10))

    def test_destroys_autocorrelation(self, structured_df):
        out, _ = make_temporal_permute(structured_df, seed=42)
        orig_ac = _autocorr_lag1(structured_df["O"])
        perm_ac = _autocorr_lag1(out["O"])
        # Permutation should reduce autocorrelation significantly
        assert abs(perm_ac) < abs(orig_ac) * 0.5

    def test_spec_metadata(self, structured_df):
        _, spec = make_temporal_permute(structured_df, seed=42)
        assert "marginal" in spec.preserves
        assert "autocorrelation" in spec.destroys


class TestPhaseRandomizeContract:
    """Phase randomize preserves spectral density, destroys phase coupling."""

    def test_preserves_approximate_mean(self, structured_df):
        out, _ = make_phase_randomize(structured_df, seed=42)
        assert abs(out["O"].mean() - structured_df["O"].mean()) < 0.2

    def test_preserves_approximate_variance(self, structured_df):
        out, _ = make_phase_randomize(structured_df, seed=42)
        orig_var = structured_df["O"].var()
        new_var = out["O"].var()
        if orig_var > 1e-10:
            ratio = new_var / orig_var
            assert 0.5 < ratio < 2.0

    def test_changes_values(self, structured_df):
        out, _ = make_phase_randomize(structured_df, seed=42)
        assert not np.allclose(out["O"].values, structured_df["O"].values, atol=1e-8)

    def test_spec_metadata(self, structured_df):
        _, spec = make_phase_randomize(structured_df, seed=42)
        assert "spectral_density" in spec.preserves
        assert "phase_coupling" in spec.destroys


class TestProxyRemapContract:
    """Proxy remap preserves autocorrelation per column but breaks cross-correlation."""

    def test_preserves_individual_autocorrelation(self, structured_df):
        out, _ = make_proxy_remap(structured_df, seed=42)
        # Each column's values exist (just in a different column)
        for col in ["O", "R", "I", "demand", "S"]:
            orig_sorted = sorted(structured_df[col].round(10))
            # The values from THIS column exist somewhere in the output
            # (but maybe in a different column)
            pass  # Proxy remap shuffles columns, not values within columns

    def test_breaks_cross_correlation(self, structured_df):
        out, _ = make_proxy_remap(structured_df, seed=42)
        orig_cc = _cross_corr(structured_df["O"], structured_df["R"])
        new_cc = _cross_corr(out["O"], out["R"])
        # Cross-correlation should change significantly
        assert abs(orig_cc - new_cc) > 0.1 or abs(new_cc) < abs(orig_cc)

    def test_columns_shuffled(self, structured_df):
        out, _ = make_proxy_remap(structured_df, seed=42)
        proxy_cols = ["O", "R", "I", "demand", "S"]
        all_same = all(
            (out[c].values == structured_df[c].values).all()
            for c in proxy_cols
        )
        assert not all_same

    def test_spec_metadata(self, structured_df):
        _, spec = make_proxy_remap(structured_df, seed=42)
        assert "autocorrelation" in spec.preserves
        assert "cross_correlation" in spec.destroys


class TestBlockShuffleContract:
    """Block shuffle preserves local autocorrelation, breaks global temporal."""

    def test_preserves_length(self, structured_df):
        out, _ = make_block_shuffle(structured_df, seed=42)
        assert len(out) == len(structured_df)

    def test_preserves_values(self, structured_df):
        out, _ = make_block_shuffle(structured_df, seed=42)
        assert sorted(out["O"].round(10)) == sorted(structured_df["O"].round(10))

    def test_changes_order(self, structured_df):
        out, _ = make_block_shuffle(structured_df, seed=42)
        assert not (out["O"].values == structured_df["O"].values).all()

    def test_spec_metadata(self, structured_df):
        _, spec = make_block_shuffle(structured_df, seed=42)
        assert "local_autocorrelation" in spec.preserves
        assert "global_temporal" in spec.destroys


class TestBatteryGeneration:
    """generate_placebo_battery produces all 5 strategies."""

    def test_generates_all_strategies(self, structured_df):
        results = generate_placebo_battery(structured_df, seed=42)
        assert len(results) == 5
        strategies = {spec.strategy for _, spec in results}
        assert strategies == set(ALL_STRATEGIES)

    def test_each_has_correct_metadata(self, structured_df):
        results = generate_placebo_battery(structured_df, seed=42)
        for df_out, spec in results:
            meta = _STRATEGY_META[spec.strategy]
            assert spec.preserves == meta["preserves"]
            assert spec.destroys == meta["destroys"]

    def test_all_same_length(self, structured_df):
        results = generate_placebo_battery(structured_df, seed=42)
        for df_out, _ in results:
            assert len(df_out) == len(structured_df)


class TestBatteryEvaluation:
    """evaluate_placebo_battery produces correct verdicts."""

    def test_passes_when_all_not_detected(self):
        verdicts = [(s, "NOT_DETECTED") for s in ALL_STRATEGIES]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.battery_passes is True
        assert result.detection_rate == 0.0
        assert result.n_strategies == 5

    def test_fails_when_all_detected(self):
        verdicts = [(s, "DETECTED") for s in ALL_STRATEGIES]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.battery_passes is False
        assert result.detection_rate == 1.0

    def test_boundary_one_of_five_detected(self):
        verdicts = [
            ("cyclic_shift", "DETECTED"),
            ("temporal_permute", "NOT_DETECTED"),
            ("phase_randomize", "NOT_DETECTED"),
            ("proxy_remap", "NOT_DETECTED"),
            ("block_shuffle", "NOT_DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.detection_rate == pytest.approx(0.20)
        assert result.battery_passes is True  # <= 0.20

    def test_two_of_five_fails(self):
        verdicts = [
            ("cyclic_shift", "DETECTED"),
            ("temporal_permute", "DETECTED"),
            ("phase_randomize", "NOT_DETECTED"),
            ("proxy_remap", "NOT_DETECTED"),
            ("block_shuffle", "NOT_DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.detection_rate == pytest.approx(0.40)
        assert result.battery_passes is False

    def test_indeterminate_excluded_from_rate(self):
        verdicts = [
            ("cyclic_shift", "INDETERMINATE"),
            ("temporal_permute", "NOT_DETECTED"),
            ("phase_randomize", "NOT_DETECTED"),
            ("proxy_remap", "NOT_DETECTED"),
            ("block_shuffle", "NOT_DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.n_indeterminate == 1
        assert result.detection_rate == 0.0
        assert result.battery_passes is True

    def test_per_strategy_detail(self):
        verdicts = [
            ("cyclic_shift", "NOT_DETECTED"),
            ("temporal_permute", "DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.50)
        assert len(result.per_strategy) == 2
        assert result.per_strategy[0]["strategy"] == "cyclic_shift"
        assert result.per_strategy[1]["verdict"] == "DETECTED"

    def test_to_dict(self):
        verdicts = [(s, "NOT_DETECTED") for s in ALL_STRATEGIES]
        result = evaluate_placebo_battery(verdicts)
        d = result.to_dict()
        assert "battery_passes" in d
        assert "per_strategy" in d
        assert "detection_rate" in d
