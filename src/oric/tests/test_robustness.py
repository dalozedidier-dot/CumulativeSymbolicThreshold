"""test_robustness.py — Robustness tests for ORI-C.

Groups:
  A — Input validation
  B — Edge cases (empty/minimal inputs)
  C — Large input stability (n=10000)
  D — Reproducibility (same seed → same result)
  E — Serialisation round-trips
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from oric.decision import hierarchical_verdict
from oric.frozen_params import FROZEN_PARAMS
from oric.ori_core import compute_cap_projection, compute_viability
from oric.ori_core_v2 import ModelV2Config, run_variant_on_dataframe
from oric.placebo import generate_placebo
from oric.prereg import PreregSpec
from oric.proxy_spec import ColumnSpec, ProxySpec
from oric.randomization import Condition, RandomizationEngine
from oric.symbolic import compute_order_C, compute_stock_S, detect_s_star_piecewise

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_df(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Create a minimal ORI-C DataFrame with all required columns."""
    return pd.DataFrame(
        {
            "O": rng.uniform(0.1, 1.0, n),
            "R": rng.uniform(0.1, 1.0, n),
            "I": rng.uniform(0.1, 1.0, n),
            "demande_env": rng.uniform(0.0, 1.0, n),
            "survie": rng.uniform(0.0, 1.0, n),
            "energie_nette": rng.uniform(0.0, 1.0, n),
            "integrite": rng.uniform(0.0, 1.0, n),
            "persistance": rng.uniform(0.0, 1.0, n),
            "repertoire": rng.uniform(0.0, 1.0, n),
            "codification": rng.uniform(0.0, 1.0, n),
            "densite_transmission": rng.uniform(0.0, 1.0, n),
            "fidelite": rng.uniform(0.0, 1.0, n),
        }
    )


def _make_sv_df(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Create a DataFrame with S and V columns for symbolic/order tests."""
    return pd.DataFrame(
        {
            "S": rng.uniform(0.0, 1.0, n),
            "V": rng.uniform(0.0, 1.0, n),
        }
    )


# ── Group A — Input validation ────────────────────────────────────────────────


def test_hierarchical_verdict_bad_alpha():
    kwargs = dict(
        p_welch=0.005,
        boot_lo=0.1,
        boot_hi=0.5,
        boot_mid=0.3,
        mw_p=0.01,
        sesoi_threshold=0.1,
    )
    with pytest.raises(ValueError):
        hierarchical_verdict(**kwargs, alpha=1.5)
    with pytest.raises(ValueError):
        hierarchical_verdict(**kwargs, alpha=0.0)
    with pytest.raises(ValueError):
        hierarchical_verdict(**kwargs, alpha=-0.1)


def test_compute_viability_negative_omega():
    rng = np.random.default_rng(0)
    df = _make_df(10, rng)
    with pytest.raises(ValueError):
        compute_viability(df, omega=(-0.1, 0.4, 0.4, 0.3))


def test_compute_viability_zero_omega():
    rng = np.random.default_rng(0)
    df = _make_df(10, rng)
    with pytest.raises(ValueError):
        compute_viability(df, omega=(0.0, 0.0, 0.0, 0.0))


# ── Group B — Edge cases ──────────────────────────────────────────────────────


def test_compute_cap_projection_single_row():
    df = pd.DataFrame({"O": [0.5], "R": [0.6], "I": [0.7]})
    for form in ("product", "geom_mean", "weighted_sum"):
        result = compute_cap_projection(df["O"], df["R"], df["I"], form=form)
        assert len(result) == 1
        assert math.isfinite(float(result.iloc[0]))


def test_compute_sigma_empty():
    from oric.ori_core import compute_sigma

    demand = pd.Series([], dtype=float)
    cap = pd.Series([], dtype=float)
    result = compute_sigma(demand, cap)
    assert len(result) == 0


def test_compute_order_C_empty_df():
    df = pd.DataFrame({"S": pd.Series([], dtype=float), "V": pd.Series([], dtype=float)})
    result = compute_order_C(df)
    assert isinstance(result, pd.Series)
    assert len(result) == 0


def test_detect_s_star_empty_C():
    result = detect_s_star_piecewise(S=[], C=[])
    assert math.isnan(result["S_star"])


# ── Group C — Large input stability ──────────────────────────────────────────


def test_cap_projection_large_n():
    n = 10_000
    rng = np.random.default_rng(1)
    df = _make_df(n, rng)
    for form in ("product", "geom_mean", "weighted_sum"):
        result = compute_cap_projection(df["O"], df["R"], df["I"], form=form)
        assert len(result) == n


def test_symbolic_large_n():
    n = 10_000
    rng = np.random.default_rng(2)
    df = _make_df(n, rng)
    alpha_s = (0.25, 0.25, 0.25, 0.25)
    S = compute_stock_S(df, alpha_s)
    assert len(S) == n
    assert not np.any(np.isnan(S))
    assert not np.any(np.isinf(S))

    sv_df = _make_sv_df(n, rng)
    C = compute_order_C(sv_df)
    assert len(C) == n
    assert not np.any(np.isnan(C))
    assert not np.any(np.isinf(C))


def test_ori_v2_v4_large_n():
    n = 1_000
    rng = np.random.default_rng(3)
    df = _make_sv_df(n, rng)
    cfg = ModelV2Config(variant="V4", seed=42)
    result = run_variant_on_dataframe(df, "V4", cfg)
    c_col = result["C_V4"].to_numpy()
    assert len(c_col) == n
    assert not np.any(np.isnan(c_col))


# ── Group D — Reproducibility ─────────────────────────────────────────────────


def test_randomization_reproducible():
    conds = [Condition("A", {}), Condition("B", {})]
    eng1 = RandomizationEngine(master_seed=42)
    seeds1 = eng1.seeds(10)
    assign1 = eng1.assign_conditions(seeds1, conds)

    eng2 = RandomizationEngine(master_seed=42)
    seeds2 = eng2.seeds(10)
    assign2 = eng2.assign_conditions(seeds2, conds)

    assert seeds1 == seeds2
    assert assign1 == assign2


def test_placebo_reproducible():
    rng = np.random.default_rng(7)
    df = _make_df(100, rng)

    df1, _ = generate_placebo(df, strategy="temporal_permute", seed=42)
    df2, _ = generate_placebo(df, strategy="temporal_permute", seed=42)

    pd.testing.assert_frame_equal(df1, df2)


def test_ori_v2_v4_reproducible():
    rng = np.random.default_rng(8)
    df = _make_sv_df(200, rng)
    cfg = ModelV2Config(variant="V4", seed=99)

    r1 = run_variant_on_dataframe(df, "V4", cfg)
    r2 = run_variant_on_dataframe(df, "V4", cfg)

    np.testing.assert_array_equal(r1["C_V4"].to_numpy(), r2["C_V4"].to_numpy())


# ── Group E — Serialisation round-trips ──────────────────────────────────────


def test_prereg_spec_round_trip():
    spec = PreregSpec(alpha=0.05, n_min=100, window_W=30)
    d = spec.to_dict()
    reconstructed = PreregSpec(**d)
    assert reconstructed == spec
    assert reconstructed.alpha == 0.05
    assert reconstructed.n_min == 100
    assert reconstructed.window_W == 30


def test_proxy_spec_round_trip():
    col = ColumnSpec(source_column="gdp", oric_variable="O")
    spec = ProxySpec(dataset_id="test_pilot", sector="economie", columns=(col,))
    sha_before = spec.sha256()

    # Serialise to JSON string and back
    json_str = json.dumps(spec.to_dict(), sort_keys=True)
    raw = json.loads(json_str)
    cols = tuple(
        ColumnSpec(
            source_column=c["source_column"],
            oric_variable=c["oric_variable"],
            direction=c.get("direction", "positive"),
            normalization=c.get("normalization", "robust_minmax"),
            missing_strategy=c.get("missing_strategy", "linear_interp"),
            scale_lo=c.get("scale_lo"),
            scale_hi=c.get("scale_hi"),
            fragility_note=c.get("fragility_note", ""),
            manipulability_note=c.get("manipulability_note", ""),
        )
        for c in raw.get("columns", [])
    )
    reconstructed = ProxySpec(
        dataset_id=raw["dataset_id"],
        sector=raw["sector"],
        spec_version=raw.get("spec_version", "1.0"),
        time_column=raw.get("time_column", "t"),
        time_mode=raw.get("time_mode", "index"),
        columns=cols,
        normalization_global=raw.get("normalization_global", "robust_minmax"),
        notes=raw.get("notes", ""),
    )
    sha_after = reconstructed.sha256()
    assert sha_before == sha_after


def test_frozen_params_round_trip():
    params = FROZEN_PARAMS
    d = params.to_dict()
    json_str = json.dumps(d)
    loaded = json.loads(json_str)
    # Check a selection of fields
    assert loaded["alpha"] == params.alpha
    assert loaded["k"] == params.k
    assert loaded["n_steps"] == params.n_steps
    assert loaded["seed_base"] == params.seed_base
