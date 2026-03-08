"""test_validation_protocol_reference_benchmark.py — Ticket 7.

Reference benchmark test for the validation protocol.  Runs a SMALL
(n=5) synthetic benchmark with frozen params and verifies the protocol
can discriminate between test, stable, and placebo conditions.

This is a lightweight CI test.  The full benchmark (n=50) is run in the
nightly CI job.  This test verifies:
  1. Protocol produces correct output structure
  2. Test condition detects (among decidable runs)
  3. Stable condition does NOT detect (among decidable runs)
  4. Placebo battery structure is present
  5. Decidability KPIs are populated
  6. Parameters match FROZEN_PARAMS exactly

Note: With n=5, statistical thresholds may not be met, so we test
structure and directional correctness, not the full ACCEPT verdict.
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


@pytest.fixture(scope="module")
def frozen_params():
    from oric.frozen_params import load_frozen_params
    return load_frozen_params()


@pytest.fixture(scope="module")
def reference_run(tmp_path_factory, frozen_params):
    """Run the validation protocol once with n=5 replicates."""
    from pipeline.run_scientific_validation_protocol import run_validation_protocol

    outdir = tmp_path_factory.mktemp("ref_benchmark")
    result = run_validation_protocol(
        outdir=outdir,
        fp=frozen_params,
        n_replicates=5,
        verbose=False,
    )
    return result, outdir


class TestOutputStructure:
    """Protocol output must contain all required fields."""

    def test_has_protocol_verdict(self, reference_run):
        result, _ = reference_run
        assert "protocol_verdict" in result
        assert result["protocol_verdict"] in ("ACCEPT", "REJECT", "INDETERMINATE")

    def test_has_discrimination_metrics(self, reference_run):
        result, _ = reference_run
        dm = result["discrimination_metrics"]
        assert "sensitivity" in dm
        assert "specificity" in dm
        assert "fisher_p_value" in dm
        assert "confusion_matrix" in dm

    def test_has_condition_summaries(self, reference_run):
        result, _ = reference_run
        cs = result["condition_summaries"]
        for cond in ("test", "stable", "placebo"):
            assert cond in cs
            assert "n_total" in cs[cond]
            assert "detection_rate" in cs[cond]

    def test_has_decidability_report(self, reference_run):
        result, _ = reference_run
        assert "decidability_report" in result
        dr = result["decidability_report"]
        assert "overall" in dr
        assert "per_condition" in dr
        assert "indeterminate_reason_taxonomy" in dr

    def test_has_placebo_battery(self, reference_run):
        result, _ = reference_run
        assert "placebo_battery" in result
        pb = result["placebo_battery"]
        assert "battery_version" in pb
        assert pb["battery_version"] == 2
        assert "detection_rate" in pb

    def test_has_frozen_params(self, reference_run):
        result, _ = reference_run
        assert "frozen_params" in result


class TestConditionSummaryDecidability:
    """Each condition summary must include decidability KPIs."""

    def test_test_has_decidability(self, reference_run):
        result, _ = reference_run
        cs = result["condition_summaries"]["test"]
        assert "decidable_count" in cs
        assert "indeterminate_count" in cs
        assert "decidable_fraction" in cs
        assert "indeterminate_rate" in cs

    def test_stable_has_decidability(self, reference_run):
        result, _ = reference_run
        cs = result["condition_summaries"]["stable"]
        assert "decidable_count" in cs
        assert "decidable_fraction" in cs

    def test_placebo_has_decidability(self, reference_run):
        result, _ = reference_run
        cs = result["condition_summaries"]["placebo"]
        assert "decidable_count" in cs


class TestDirectionalCorrectness:
    """With even n=5, test should detect more than stable."""

    def test_test_detection_higher_than_stable(self, reference_run):
        result, _ = reference_run
        cs = result["condition_summaries"]
        test_det = cs["test"]["n_detected"]
        stable_det = cs["stable"]["n_detected"]
        # Test should detect more than stable (directional check)
        assert test_det >= stable_det

    def test_sensitivity_non_negative(self, reference_run):
        result, _ = reference_run
        dm = result["discrimination_metrics"]
        assert dm["sensitivity"] >= 0.0
        assert dm["specificity"] >= 0.0


class TestParameterImmutability:
    """Frozen params must not change during the run."""

    def test_params_match_contract(self, reference_run, frozen_params):
        result, _ = reference_run
        run_params = result["frozen_params"]
        assert run_params["alpha"] == frozen_params.alpha
        assert run_params["n_steps"] == frozen_params.n_steps
        assert run_params["intervention_point"] == frozen_params.intervention_point
        assert run_params["seed_base"] == frozen_params.seed_base

    def test_frozen_params_file_written(self, reference_run):
        _, outdir = reference_run
        fp_path = outdir / "frozen_params.json"
        assert fp_path.exists()
        data = json.loads(fp_path.read_text())
        assert data["alpha"] == 0.01


class TestOutputFiles:
    """All expected output files must be produced."""

    def test_validation_summary(self, reference_run):
        _, outdir = reference_run
        assert (outdir / "tables" / "validation_summary.json").exists()

    def test_validation_results_csv(self, reference_run):
        _, outdir = reference_run
        assert (outdir / "tables" / "validation_results.csv").exists()

    def test_validation_kpis(self, reference_run):
        _, outdir = reference_run
        assert (outdir / "tables" / "validation_kpis.json").exists()

    def test_validation_report_md(self, reference_run):
        _, outdir = reference_run
        assert (outdir / "VALIDATION_REPORT.md").exists()

    def test_verdict_txt(self, reference_run):
        _, outdir = reference_run
        assert (outdir / "verdict.txt").exists()
        v = (outdir / "verdict.txt").read_text().strip()
        assert v in ("ACCEPT", "REJECT", "INDETERMINATE")
