"""test_nightly_sector_verdict_alignment.py — End-to-end verdict alignment test.

Simulates the EXACT nightly CI execution path for sector mini-runs:
  1. run_real_data_demo.py writes summary.json with initial verdict
  2. tests_causaux.py writes verdict.json AND syncs summary.json

Verifies that after the full chain, summary.json["verdict"] always
matches the canonical verdict from verdict.json, even when:
  - tests_causaux produces French tokens (indetermine_precheck_failed)
  - the initial summary.json had verdict=ACCEPT
  - prechecks fail
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
_CODE_DIR = _REPO_ROOT / "04_Code"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from pipeline.tests_causaux import _sync_summary_after_verdict, _normalize_verdict_token


class TestNormalizeVerdictToken:
    """French tokens from tests_causaux must normalise to English."""

    @pytest.mark.parametrize("raw,expected", [
        ("ACCEPT", "ACCEPT"),
        ("REJECT", "REJECT"),
        ("INDETERMINATE", "INDETERMINATE"),
        ("seuil_detecte", "ACCEPT"),
        ("non_detecte", "REJECT"),
        ("falsifie", "REJECT"),
        ("indetermine_precheck_failed:min_variance_C (var_pre=0.00e+00, var_post=0.00e+00)", "INDETERMINATE"),
        ("indetermine_precheck_failed:min_unique_values_C (pre=1, post=1, min=5)", "INDETERMINATE"),
        ("indetermine_precheck_failed:min_points_per_segment (pre=15<60)", "INDETERMINATE"),
        (None, "INDETERMINATE"),
        ("", "INDETERMINATE"),
    ])
    def test_normalize(self, raw, expected):
        assert _normalize_verdict_token(raw) == expected


class TestSyncSummaryAfterVerdict:
    """_sync_summary_after_verdict must fix summary.json in all scenarios."""

    def _setup_summary(self, tabdir, summary_data):
        tabdir.mkdir(parents=True, exist_ok=True)
        (tabdir / "summary.json").write_text(
            json.dumps(summary_data), encoding="utf-8"
        )

    def test_precheck_failed_overrides_accept(self, tmp_path):
        """The exact bug: summary=ACCEPT but verdict=indetermine_precheck_failed."""
        tabdir = tmp_path / "tables"
        self._setup_summary(tabdir, {
            "verdict": "ACCEPT",
            "run_mode": "real_data_canonical",
        })

        report = {
            "verdict": "indetermine_precheck_failed:min_variance_C (var_pre=0.00e+00)",
            "precheck_passed": False,
            "precheck_reason": "precheck_failed:min_variance_C",
        }
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE"
        assert s["precheck_passed"] is False
        assert s["verdict_source"] == "tests_causaux.verdict.json"
        assert "verdict_raw" in s

    def test_seuil_detecte_normalised_to_accept(self, tmp_path):
        tabdir = tmp_path / "tables"
        self._setup_summary(tabdir, {"verdict": "INDETERMINATE"})

        report = {"verdict": "seuil_detecte", "precheck_passed": True}
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "ACCEPT"

    def test_non_detecte_normalised_to_reject(self, tmp_path):
        tabdir = tmp_path / "tables"
        self._setup_summary(tabdir, {"verdict": "ACCEPT"})

        report = {"verdict": "non_detecte"}
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "REJECT"

    def test_already_canonical_accept(self, tmp_path):
        tabdir = tmp_path / "tables"
        self._setup_summary(tabdir, {"verdict": "REJECT"})

        report = {"verdict": "seuil_detecte", "precheck_passed": True}
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "ACCEPT"

    def test_preserves_other_fields(self, tmp_path):
        tabdir = tmp_path / "tables"
        self._setup_summary(tabdir, {
            "verdict": "ACCEPT",
            "run_mode": "real_data_canonical",
            "n_steps": 480,
            "C_mean": 0.42,
        })

        report = {
            "verdict": "indetermine_precheck_failed:min_unique_values_C",
            "precheck_passed": False,
        }
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE"
        assert s["run_mode"] == "real_data_canonical"
        assert s["n_steps"] == 480
        assert s["C_mean"] == 0.42

    def test_no_summary_does_nothing(self, tmp_path):
        """If summary.json doesn't exist, no error."""
        tabdir = tmp_path / "tables"
        tabdir.mkdir(parents=True)
        report = {"verdict": "seuil_detecte"}
        _sync_summary_after_verdict(tabdir, report)  # Should not raise

    def test_precheck_false_accept_verdict_overridden(self, tmp_path):
        """If precheck_passed=False but verdict was somehow ACCEPT, override."""
        tabdir = tmp_path / "tables"
        self._setup_summary(tabdir, {"verdict": "ACCEPT"})

        # Pathological case: seuil_detecte but precheck failed
        report = {
            "verdict": "seuil_detecte",
            "precheck_passed": False,
        }
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE"
        assert "verdict_override_reason" in s


class TestSimulatedNightlyChain:
    """Simulate the exact nightly CI execution path."""

    def test_full_chain_precheck_failure(self, tmp_path):
        """
        Step 1: run_real_data_demo.py writes summary.json with verdict=ACCEPT
        Step 2: tests_causaux.py writes verdict.json with indetermine_precheck_failed
                AND calls _sync_summary_after_verdict
        Result: summary.json["verdict"] must be INDETERMINATE
        """
        tabdir = tmp_path / "tables"
        tabdir.mkdir(parents=True)

        # Step 1: run_real_data_demo.py output
        summary = {
            "input_csv": "03_Data/real/transport/pilot_trafic/real.csv",
            "n_steps": 120,
            "verdict": "ACCEPT",
            "run_mode": "real_data_canonical",
        }
        (tabdir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        # Step 2: tests_causaux.py writes verdict.json
        report = {
            "verdict": "indetermine_precheck_failed:min_variance_C (var_pre=0.00e+00, var_post=0.00e+00)",
            "precheck_passed": False,
            "precheck_reason": "precheck_failed:min_variance_C",
            "detection_strength": 0.0,
        }
        (tabdir / "verdict.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

        # tests_causaux.py also calls this right after writing verdict.json
        _sync_summary_after_verdict(tabdir, report)

        # Verify: summary.json must now match canonical verdict
        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE", (
            f"summary.json['verdict'] should be INDETERMINATE, got {s['verdict']}"
        )
        assert s["precheck_passed"] is False
        assert s["verdict_source"] == "tests_causaux.verdict.json"
        assert s["verdict_raw"] == report["verdict"]

    def test_full_chain_detection(self, tmp_path):
        """
        Step 1: run_real_data_demo.py writes summary.json with verdict=ACCEPT
        Step 2: tests_causaux.py confirms with seuil_detecte
        Result: summary.json["verdict"] must be ACCEPT
        """
        tabdir = tmp_path / "tables"
        tabdir.mkdir(parents=True)

        summary = {
            "verdict": "ACCEPT",
            "run_mode": "real_data_canonical",
        }
        (tabdir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        report = {
            "verdict": "seuil_detecte",
            "precheck_passed": True,
        }
        (tabdir / "verdict.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "ACCEPT"

    def test_full_chain_non_detecte(self, tmp_path):
        """
        Step 1: run_real_data_demo.py writes summary.json with verdict=ACCEPT
        Step 2: tests_causaux.py says non_detecte
        Result: summary.json["verdict"] must be REJECT
        """
        tabdir = tmp_path / "tables"
        tabdir.mkdir(parents=True)

        summary = {"verdict": "ACCEPT", "run_mode": "real_data_canonical"}
        (tabdir / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        report = {"verdict": "non_detecte", "precheck_passed": True}
        (tabdir / "verdict.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        _sync_summary_after_verdict(tabdir, report)

        s = json.loads((tabdir / "summary.json").read_text())
        assert s["verdict"] == "REJECT"
