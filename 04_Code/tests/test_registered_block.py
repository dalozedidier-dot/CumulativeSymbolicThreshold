"""Tests for the frozen registered real-data A/B/C block."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from oric.registered_block import (
    BlockCriteria,
    derive_controls,
    pelt_changepoint,
    run_registered_block,
)

_CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "REAL_DATA_REGISTRATION.json"
_TOKENS = {"REAL_BLOCK_CONFIRMED", "REAL_BLOCK_REJECTED", "REAL_BLOCK_INDETERMINATE"}


# ── PELT (dependency-free) ────────────────────────────────────────────────────

def test_pelt_detects_a_step_and_is_silent_on_flat():
    rng = np.random.default_rng(0)
    step = np.concatenate([np.zeros(80), np.full(80, 5.0)]) + rng.normal(0, 0.3, 160)
    flat = rng.normal(0, 1.0, 160)
    rs = pelt_changepoint(step)
    assert rs["detected"] and abs(rs["detection_point"] - 80) <= 8
    assert pelt_changepoint(flat)["detected"] is False


def test_pelt_short_series_is_safe():
    assert pelt_changepoint(np.arange(5.0))["detected"] is False


# ── Controls ──────────────────────────────────────────────────────────────────

def _synth_A(n: int = 160, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    demand = np.where(t < 90, 0.6, 1.5) + rng.normal(0, 0.03, n)  # localized step at 90
    return pd.DataFrame({
        "t": t,
        "O": np.clip(0.62 + rng.normal(0, 0.015, n), 0.05, 0.95),
        "R": np.clip(0.66 + rng.normal(0, 0.015, n), 0.05, 0.95),
        "I": np.clip(0.58 + rng.normal(0, 0.015, n), 0.05, 0.95),
        "demand": demand,
        "S": np.clip(0.3 + 0.001 * t, 0, 1),
    })


def test_derive_controls_shapes():
    A = _synth_A(160)
    ctrl = derive_controls(A, t1=90, shift_divisor=3)
    assert len(ctrl["stable"]) == 90              # pre-onset segment
    assert len(ctrl["placebo"]) == len(A)         # cyclic shift keeps length
    # placebo is a permutation of A's demand (same multiset), reordered
    assert np.allclose(sorted(ctrl["placebo"]["demand"]), sorted(A["demand"]))


# ── End-to-end ────────────────────────────────────────────────────────────────

def test_block_runs_and_returns_a_valid_verdict():
    A = _synth_A(160)
    contract = {
        "dataset_A": {"id": "synthetic"},
        "dated_hypothesis": {"t1": 90, "t2": 100, "t_star": 90, "label": "synthetic step"},
        "criteria": {"k": 2.5, "m": 3, "baseline_n": 40, "alpha": 0.01,
                     "seed": 7, "n_surrogates": 20, "onset_tolerance": 18, "shift_divisor": 3},
    }
    res = run_registered_block(contract, {"A": A}, fast=True)
    assert res["schema"] == "oric.registered_block.v1"
    assert res["verdict"] in _TOKENS
    # Structural invariants of the result.
    for key in ("A", "B_silent", "C_silent", "surrogate", "classical", "oos", "reasons"):
        assert key in res
    assert isinstance(res["surrogate"]["p_value"], float)
    assert set(res["classical"]) == {"A", "B_stable", "C_placebo"}
    for panel in res["classical"].values():
        assert {"cusum_changepoint", "pelt_changepoint",
                "early_warning_signal", "structural_break"} <= set(panel)


# ── Contract <-> code consistency ─────────────────────────────────────────────

def test_contract_is_frozen_and_consistent():
    c = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    assert c["schema"] == "oric.real_data_registration.v1"
    assert c["status"] == "FROZEN"
    assert set(c["verdict_tokens"]) == _TOKENS
    # Every criteria key must be a real BlockCriteria field (no silent typos).
    valid = set(BlockCriteria().__dict__)
    assert set(c["criteria"]).issubset(valid)
    # The dated hypothesis is fully specified and ordered.
    h = c["dated_hypothesis"]
    assert h["t1"] <= h["t2"] and h["t_star"] >= 0
    # The classical panel the contract pins must match what the code runs.
    assert set(c["classical_benchmarks"]) == {
        "cusum_changepoint", "pelt_changepoint", "early_warning_signal", "structural_break"}


def test_contract_criteria_construct_blockcriteria():
    c = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    cr = BlockCriteria(**c["criteria"])   # must not raise
    assert cr.k == 2.5 and cr.m == 3 and cr.baseline_n == 50
