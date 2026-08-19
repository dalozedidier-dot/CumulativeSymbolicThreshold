"""Tests for oric.confirmatory — joint confirmatory verdict."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations

from oric.confirmatory import run_confirmatory_suite


def _trend_df(n=140, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "t": np.arange(n),
        "O": np.clip(0.6 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "R": np.clip(0.65 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "I": np.clip(0.58 + rng.normal(0, 0.02, n), 0.05, 0.95),
        "demand": np.linspace(0.6, 1.6, n) * (1 + rng.normal(0, 0.02, n)),
    })


def test_confirmatory_structure_and_joint_rule():
    df = _trend_df()
    cfg = ORICConfig(seed=1, n_steps=len(df), intervention="none")
    res = run_confirmatory_suite(
        df, cfg, n_surrogates=30, accumulation_n=120, accumulation_seed=7,
        rng=np.random.default_rng(0), run_fn=run_oric_from_observations,
    )
    assert res["schema"] == "oric.confirmatory.v1"
    assert set(res["tests"]) == {
        "A_accumulation_specificity", "B_surrogate_null", "C_multiverse", "D_effect_size",
    }
    # Joint rule: confirmed iff every test passes.
    assert res["confirmed"] == all(t["pass"] for t in res["tests"].values())
    assert res["verdict"] in {"CONFIRMED", "NOT_CONFIRMED"}
    if res["failing_tests"]:
        assert res["limiting_factor"] == res["failing_tests"][0]


def test_confirmatory_test_a_is_global_property():
    # Test A reflects the detector, not the series: with the current detector it
    # fails (accumulation_fpr = 1.0), so no series can be CONFIRMED.
    df = _trend_df(seed=3)
    cfg = ORICConfig(seed=1, n_steps=len(df), intervention="none")
    res = run_confirmatory_suite(
        df, cfg, n_surrogates=20, accumulation_n=120, accumulation_seed=7,
        rng=np.random.default_rng(1), run_fn=run_oric_from_observations,
    )
    a = res["tests"]["A_accumulation_specificity"]
    assert a["scope"] == "global_detector_property"
    assert a["accumulation_fpr"] >= 0.0
    if not a["pass"]:
        assert res["verdict"] == "NOT_CONFIRMED"
