"""Tests for oric.strong_negatives — the strong-negatives specificity battery.

These tests lock the *specificity* half of the proof: the localized-transition
gate must stay silent on adversarial non-transition processes (unit-root random
walk, AR(1) red noise, 1/f noise, sinusoid, sawtooth, smooth accumulations) while
still flagging genuine bifurcations.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from oric.strong_negatives import (
    FPR_MAX,
    TPR_MIN,
    STOCHASTIC_NEGATIVES,
    STRUCTURED_NEGATIVES,
    gen_strong_negative,
    strong_negatives_catalogue,
    run_strong_negatives_suite,
)

_CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "STRONG_NEGATIVES_CRITERIA.json"


# ── Generators ────────────────────────────────────────────────────────────────

def test_strong_negative_generators_produce_pipeline_columns():
    for kind in STOCHASTIC_NEGATIVES + STRUCTURED_NEGATIVES:
        df = gen_strong_negative(kind, n=160, seed=3)
        assert {"t", "O", "R", "I", "demand"}.issubset(df.columns)
        assert len(df) == 160
        assert np.isfinite(df["demand"].to_numpy()).all()


def test_random_walk_is_not_a_clean_monotone_trend():
    """A unit-root random walk should NOT be a strong monotone trend like a ramp
    (it is the adversarial 'spurious trend' case, not a deterministic ramp)."""
    d = gen_strong_negative("random_walk", n=240, seed=5)["demand"].to_numpy()
    rho, _ = spearmanr(np.arange(d.size), d)
    assert abs(rho) < 0.98  # not a near-perfect deterministic trend


def test_white_noise_is_stationary_band():
    d = gen_strong_negative("white_noise", n=240, seed=5)["demand"].to_numpy()
    # No strong monotone drift in a stationary band.
    rho, _ = spearmanr(np.arange(d.size), d)
    assert abs(rho) < 0.5


# ── Catalogue ─────────────────────────────────────────────────────────────────

def test_catalogue_has_negatives_and_positive_contrast():
    cat = strong_negatives_catalogue(n=120, seed=1)
    negs = [e for e in cat if e.label == 0]
    poss = [e for e in cat if e.label == 1]
    # 4 smooth + 5 stochastic + 2 structured = 11 negatives; 2 positives
    assert len(negs) == 11
    assert len(poss) == 2
    families = {e.family for e in negs}
    assert {"smooth", "stochastic", "structured"} <= families
    for e in cat:
        assert {"t", "O", "R", "I", "demand"}.issubset(e.df.columns)


# ── Suite metrics ─────────────────────────────────────────────────────────────

def test_suite_runs_and_reports_valid_metrics():
    res = run_strong_negatives_suite(n=140, seed=1234, n_surrogates=0)
    assert res["schema"] == "oric.strong_negatives.v1"
    assert res["n_negatives"] == 11
    assert res["n_positives"] == 2
    for key in ("strong_negatives_fpr", "raw_strong_negatives_fpr", "bifurcation_tpr"):
        assert 0.0 <= res[key] <= 1.0
    assert res["verdict"] in {
        "STRONG_NEGATIVES_CLEAN", "STRONG_NEGATIVES_LEAK", "STRONG_NEGATIVES_INSENSITIVE"
    }


def test_localized_gate_is_at_least_as_specific_as_bare_gate():
    """The whole point: the localized gate must suppress, never amplify, the bare
    sustained-crossing gate's false positives on the negatives."""
    res = run_strong_negatives_suite(n=220, seed=1234, n_surrogates=0)
    assert res["strong_negatives_fpr"] <= res["raw_strong_negatives_fpr"]


def test_shipped_battery_is_clean_and_sensitive():
    """Frozen, reproducible behaviour on the shipped seed (contract-backed)."""
    res = run_strong_negatives_suite(n=220, seed=1234, n_surrogates=0)
    assert res["strong_negatives_fpr"] <= FPR_MAX          # specific
    assert res["bifurcation_tpr"] >= TPR_MIN               # still sensitive
    assert res["verdict"] == "STRONG_NEGATIVES_CLEAN"
    # The bare gate demonstrably leaks (>= a third of the battery), proving the
    # negatives are genuinely adversarial and the localized gate is doing work.
    assert res["raw_strong_negatives_fpr"] >= 0.33


# ── Contract consistency ──────────────────────────────────────────────────────

def test_contract_matches_module_thresholds():
    contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    assert contract["fpr_max"] == FPR_MAX
    assert contract["tpr_min"] == TPR_MIN
    assert contract["shipped_result"]["verdict"] == "STRONG_NEGATIVES_CLEAN"
