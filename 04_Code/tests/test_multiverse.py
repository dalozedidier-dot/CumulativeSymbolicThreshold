"""Tests for oric.multiverse — specification-curve / multiverse robustness."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations

from oric.multiverse import (
    DEMAND_RATIO_CHOICES,
    NORMALIZE_CHOICES,
    SMOOTH_CHOICES,
    Specification,
    apply_specification,
    run_multiverse,
    specification_grid,
)


def _df(n=160, kind="trend", seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    base = {
        "O": np.clip(0.6 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "R": np.clip(0.65 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "I": np.clip(0.58 + rng.normal(0, 0.02, n), 0.05, 0.95),
    }
    if kind == "trend":
        demand = np.linspace(0.6, 1.6, n) * (1 + rng.normal(0, 0.02, n))
    else:  # noise
        demand = np.clip(0.4 + rng.normal(0, 0.1, n), 0.01, 1.0)
    return pd.DataFrame({"t": t, **base, "demand": demand})


def test_specification_grid_is_full_cartesian():
    grid = specification_grid()
    assert len(grid) == len(NORMALIZE_CHOICES) * len(SMOOTH_CHOICES) * len(DEMAND_RATIO_CHOICES)
    assert len(grid) == 27
    assert len({s.label for s in grid}) == 27  # all unique


def test_apply_specification_keeps_proxies_in_unit_band():
    df = _df()
    spec = Specification("zscore", "ma5", 0.90)
    out = apply_specification(df, spec)
    for col in ("O", "R", "I", "demand"):
        v = out[col].to_numpy()
        assert np.all(v >= 0.02) and np.all(v <= 0.98)
    # t preserved
    np.testing.assert_array_equal(out["t"].to_numpy(), df["t"].to_numpy())


def test_smoothing_increases_autocorrelation():
    # After min-max rescaling, variance is re-stretched, but smoothing's effect on
    # lag-1 autocorrelation (scale-invariant) persists: smoothing raises it.
    df = _df(kind="noise", seed=3)
    raw = apply_specification(df, Specification("minmax", "none", 0.90))["demand"].to_numpy()
    sm = apply_specification(df, Specification("minmax", "ma5", 0.90))["demand"].to_numpy()

    def ac1(x: np.ndarray) -> float:
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])

    assert ac1(sm) > ac1(raw)


def test_run_multiverse_structure_and_tokens():
    df = _df(kind="trend")
    cfg = ORICConfig(seed=1, n_steps=len(df), intervention="none")
    res = run_multiverse(df, cfg, run_fn=run_oric_from_observations)
    assert res["schema"] == "oric.multiverse.v1"
    assert res["n_specs"] == 27
    assert len(res["outcomes"]) == 27
    assert 0.0 <= res["fired_fraction"] <= 1.0
    assert res["robustness"] in {"ROBUST_POSITIVE", "ROBUST_NEGATIVE", "FRAGILE"}
    q = res["crossing_rate_quartiles"]
    assert q["min"] <= q["median"] <= q["max"]


def test_run_multiverse_subset_specs():
    df = _df()
    cfg = ORICConfig(seed=1, n_steps=len(df), intervention="none")
    specs = [Specification("robust_minmax", "none", 0.90),
             Specification("zscore", "ma3", 0.85)]
    res = run_multiverse(df, cfg, specs=specs, run_fn=run_oric_from_observations)
    assert res["n_specs"] == 2
    assert len(res["outcomes"]) == 2
