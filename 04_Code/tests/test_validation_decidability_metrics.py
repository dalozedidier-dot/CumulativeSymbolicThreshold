"""test_validation_decidability_metrics.py — Ticket 5.

Tests that the validation protocol produces explicit decidability metrics
and reason taxonomies per condition (test/stable/placebo).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from oric.decidability import (
    compute_decidability,
    build_decidability_report,
    DecidabilityMetrics,
)


class TestDecidabilityKPIs:
    """Validation protocol must publish decidability metrics per condition."""

    def _make_runs(self, verdicts: list[str], reasons: list[str | None] = None):
        if reasons is None:
            reasons = [None] * len(verdicts)
        return [
            {"verdict": v, "precheck_reason": r}
            for v, r in zip(verdicts, reasons)
        ]

    def test_all_decidable_test_condition(self):
        runs = self._make_runs(["DETECTED"] * 8 + ["NOT_DETECTED"] * 2)
        m = compute_decidability(runs, condition="test")
        assert m.n_total == 10
        assert m.n_decidable == 10
        assert m.decidable_fraction == 1.0
        assert m.indeterminate_rate == 0.0
        assert m.detection_rate == 0.8

    def test_mixed_stable_with_reasons(self):
        verdicts = (
            ["NOT_DETECTED"] * 5
            + ["INDETERMINATE"] * 4
            + ["DETECTED"]
        )
        reasons = (
            [None] * 5
            + ["min_variance"] * 2
            + ["min_unique"] * 2
            + [None]
        )
        m = compute_decidability(
            self._make_runs(verdicts, reasons), condition="stable"
        )
        assert m.n_total == 10
        assert m.n_decidable == 6
        assert m.n_indeterminate == 4
        assert m.decidable_fraction == pytest.approx(0.6)
        assert m.indeterminate_rate == pytest.approx(0.4)
        assert m.indeterminate_reasons["min_variance"] == 2
        assert m.indeterminate_reasons["min_unique"] == 2
        assert m.top_indeterminate_reason == "min_variance"

    def test_all_indeterminate_placebo(self):
        runs = self._make_runs(
            ["INDETERMINATE"] * 10,
            ["precheck_failed:too_short"] * 10,
        )
        m = compute_decidability(runs, condition="placebo")
        assert m.n_decidable == 0
        assert m.indeterminate_rate == 1.0
        assert m.detection_rate == 0.0  # No decidable runs

    def test_empty_runs(self):
        m = compute_decidability([], condition="test")
        assert m.n_total == 0
        assert m.decidable_fraction == 0.0


class TestDecidabilityReport:
    """build_decidability_report must produce a structured report."""

    def test_full_report_structure(self):
        test_m = DecidabilityMetrics(
            condition="test", n_total=50, n_decidable=48,
            n_detected=45, n_not_detected=3, n_indeterminate=2,
        )
        test_m.decidable_fraction = 48 / 50
        test_m.detection_rate = 45 / 48
        test_m.non_detection_rate = 3 / 48
        test_m.indeterminate_rate = 2 / 50

        stable_m = DecidabilityMetrics(
            condition="stable", n_total=50, n_decidable=35,
            n_detected=2, n_not_detected=33, n_indeterminate=15,
            indeterminate_reasons={"min_variance": 10, "min_unique": 5},
            top_indeterminate_reason="min_variance",
        )
        stable_m.decidable_fraction = 35 / 50
        stable_m.detection_rate = 2 / 35
        stable_m.non_detection_rate = 33 / 35
        stable_m.indeterminate_rate = 15 / 50

        placebo_m = DecidabilityMetrics(
            condition="placebo", n_total=50, n_decidable=40,
            n_detected=5, n_not_detected=35, n_indeterminate=10,
        )
        placebo_m.decidable_fraction = 40 / 50
        placebo_m.detection_rate = 5 / 40
        placebo_m.non_detection_rate = 35 / 40
        placebo_m.indeterminate_rate = 10 / 50

        report = build_decidability_report(test_m, stable_m, placebo_m)

        # Required structure
        assert "overall" in report
        assert "per_condition" in report
        assert "indeterminate_reason_taxonomy" in report
        assert "recommendations" in report
        assert "stable_decides_non_detection" in report
        assert "key_phrase" in report

        # Overall counts
        overall = report["overall"]
        assert overall["n_total"] == 150
        assert overall["n_decidable"] == 48 + 35 + 40
        assert overall["n_indeterminate"] == 2 + 15 + 10

        # Per condition
        assert "test" in report["per_condition"]
        assert "stable" in report["per_condition"]
        assert "placebo" in report["per_condition"]

        # Reason taxonomy aggregated
        assert "min_variance" in report["indeterminate_reason_taxonomy"]

    def test_stable_decides_non_detection_flag(self):
        """When stable has high decidability and low detection → True."""
        test_m = DecidabilityMetrics(condition="test", n_total=10, n_decidable=10)
        test_m.decidable_fraction = 1.0

        stable_m = DecidabilityMetrics(
            condition="stable", n_total=10, n_decidable=8,
            n_detected=0, n_not_detected=8,
        )
        stable_m.decidable_fraction = 0.80
        stable_m.non_detection_rate = 1.0

        placebo_m = DecidabilityMetrics(condition="placebo", n_total=10, n_decidable=8)
        placebo_m.decidable_fraction = 0.80

        report = build_decidability_report(test_m, stable_m, placebo_m)
        assert report["stable_decides_non_detection"] is True
        assert "protocol decides majority NOT_DETECTED" in report["key_phrase"]

    def test_low_stable_decidability_recommendation(self):
        """Low stable decidability triggers a recommendation."""
        test_m = DecidabilityMetrics(condition="test", n_total=10, n_decidable=10)
        test_m.decidable_fraction = 1.0

        stable_m = DecidabilityMetrics(
            condition="stable", n_total=10, n_decidable=2,
        )
        stable_m.decidable_fraction = 0.20

        placebo_m = DecidabilityMetrics(condition="placebo", n_total=10, n_decidable=8)
        placebo_m.decidable_fraction = 0.80

        report = build_decidability_report(test_m, stable_m, placebo_m)
        assert any("stable decidability low" in r for r in report["recommendations"])

    def test_high_placebo_detection_recommendation(self):
        """High placebo detection triggers a recommendation."""
        test_m = DecidabilityMetrics(condition="test", n_total=10, n_decidable=10)
        test_m.decidable_fraction = 1.0

        stable_m = DecidabilityMetrics(condition="stable", n_total=10, n_decidable=10)
        stable_m.decidable_fraction = 1.0

        placebo_m = DecidabilityMetrics(
            condition="placebo", n_total=10, n_decidable=10,
            n_detected=8, n_not_detected=2,
        )
        placebo_m.decidable_fraction = 1.0
        placebo_m.detection_rate = 0.80

        report = build_decidability_report(test_m, stable_m, placebo_m)
        assert any("placebo detection rate too high" in r for r in report["recommendations"])
