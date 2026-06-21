"""test_endogenous_full_statistical.py — Smoke test for the full_statistical run (axis 4).

Runs the proof-run script with a tiny N in a temp dir and checks the output
schema and the obligatory-triplet fields. The full N=50 run is executed and
stored separately under 05_Results/.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "04_Code" / "pipeline" / "run_endogenous_full_statistical.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_endogenous_full_statistical", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_full_statistical_smoke(tmp_path, monkeypatch):
    runner = _load_runner()
    out = tmp_path / "efs"
    monkeypatch.setattr(sys, "argv", [
        "run_endogenous_full_statistical.py", "--outdir", str(out),
        "--n-replicates", "4", "--n-surrogates", "5", "--n-steps", "800",
    ])
    assert runner.main() == 0

    data = json.loads((out / "tables" / "full_statistical.json").read_text())
    assert data["run_mode"] == "full_statistical"
    assert data["model"] == "endogenous_bistable"
    # obligatory triplet present
    for key in ("p_value_mann_whitney", "standardised_effect", "ci99",
                "sesoi_robust_sd", "achieved_power_at_sesoi"):
        assert key in data["triplet"]
    # corroborating signatures: bistable hysteresis loop dwarfs the twin's
    sig = data["bifurcation_signatures"]
    assert sig["hysteresis_area_bistable"] > 5 * sig["hysteresis_area_twin"]
    assert sig["steady_state_jump_bistable"] > sig["steady_state_jump_twin"]
    assert data["verdict"] in ("DEMONSTRATION_CONFIRMED", "DEMONSTRATION_NOT_CONFIRMED")
    assert (out / "manifest.json").exists()
    assert (out / "verdict.txt").exists()


def test_steady_state_jump_zero_for_twin():
    runner = _load_runner()
    from oric.endogenous import EndogenousConfig
    cfg = EndogenousConfig()
    assert runner._steady_state_jump(cfg) > 1.0           # bistable: real jump
    assert runner._steady_state_jump(cfg.linear_twin()) == pytest.approx(0.0)  # twin: none
