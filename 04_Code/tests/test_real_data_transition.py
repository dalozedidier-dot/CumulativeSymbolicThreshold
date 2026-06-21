"""test_real_data_transition.py — Real data with a ground-truth onset (axis 6).

Verifies the variance-shift detector locates a known regime onset and that the
Bonn EEG seizure-onset demonstration passes (detector fires at the ictal onset,
quiet on matched non-seizure controls).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "04_Code" / "pipeline" / "run_real_data_transition.py"
_BONN = _REPO / "03_Data" / "sector_neuro" / "real" / "pilot_eeg_bonn" / "real.csv"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_real_data_transition", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDetector:
    def test_variance_shift_and_onset(self):
        runner = _load_runner()
        rng = np.random.default_rng(0)
        # Flat low-variance segment then a high-variance burst at index 300.
        x = np.concatenate([rng.normal(0, 1.0, 300), rng.normal(0, 6.0, 200)])
        assert runner.variance_shift_stat(x, 30) > 5.0
        assert abs(runner.detect_onset(x, 30) - 300) <= 40

    def test_flat_series_low_shift(self):
        runner = _load_runner()
        x = np.random.default_rng(1).normal(0, 1.0, 500)
        assert runner.variance_shift_stat(x, 30) < 5.0


class TestBonnOnset:
    def test_seizure_onset_demonstration(self, tmp_path, monkeypatch):
        if not _BONN.exists():
            import pytest
            pytest.skip("Bonn EEG data not present")
        runner = _load_runner()
        out = tmp_path / "rdt"
        monkeypatch.setattr(sys, "argv", [
            "run_real_data_transition.py", "--outdir", str(out), "--fast",
        ])
        assert runner.main() == 0
        data = json.loads((out / "tables" / "real_data_transition.json").read_text())
        # Detector locates the ictal onset and separates seizure from controls.
        assert data["seizure_series"]["onset_within_tolerance"]
        assert data["seizure_series"]["statistic"] > 10.0
        for ctrl in data["controls"].values():
            assert ctrl["statistic"] < data["seizure_series"]["statistic"]
        assert data["verdict"] == "REAL_ONSET_CONFIRMED"
