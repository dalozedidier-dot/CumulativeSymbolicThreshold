"""test_proof_infrastructure.py — Tests for the complete proof infrastructure.

Tests for:
  1. proof_manifest: DualProofManifest builder, completeness checks, final_status
  2. integrity: verdict alignment, precheck/ACCEPT conflict, dual proof consistency
  3. placebo: all 5 strategies, battery evaluation
  4. decidability: metrics computation, adapted prechecks, decidability report
  5. proof_levels: Level A/B classification, summary
  6. proof_package: 4-bloc package builder, overall verdict
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ═══════════════════════════════════════════════════════════════════════════
# 1. proof_manifest
# ═══════════════════════════════════════════════════════════════════════════

from oric.proof_manifest import (
    DualProofManifest,
    build_dual_proof_manifest,
    build_final_status,
    _is_empty,
)


class TestIsEmpty:
    def test_none_is_empty(self):
        assert _is_empty(None)

    def test_empty_string_is_empty(self):
        assert _is_empty("")
        assert _is_empty("  ")

    def test_nan_is_empty(self):
        assert _is_empty(float("nan"))

    def test_valid_values_not_empty(self):
        assert not _is_empty("ACCEPT")
        assert not _is_empty(0)
        assert not _is_empty(0.5)
        assert not _is_empty(False)


class TestDualProofManifest:
    def test_empty_manifest_is_incomplete(self):
        m = DualProofManifest()
        m.check_completeness()
        assert m.dual_proof_status == "DUAL_PROOF_INCOMPLETE"
        assert len(m.empty_fields) > 0

    def test_complete_manifest(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
            validation_sensitivity=0.92,
            validation_specificity=0.88,
        )
        m.check_completeness()
        assert m.dual_proof_status == "DUAL_PROOF_COMPLETE"
        assert len(m.empty_fields) == 0
        assert len(m.inconsistencies) == 0

    def test_inconsistency_synthetic_accept_but_gate_false(self):
        m = DualProofManifest(
            synthetic_gate_passed=False,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
        )
        m.check_completeness()
        assert m.dual_proof_status == "DUAL_PROOF_INCOMPLETE"
        assert any("gate_passed" in i for i in m.inconsistencies)

    def test_inconsistency_accept_but_low_sensitivity(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
            validation_sensitivity=0.50,
        )
        m.check_completeness()
        assert m.dual_proof_status == "DUAL_PROOF_INCOMPLETE"
        assert any("sensitivity" in i for i in m.inconsistencies)

    def test_serialization_roundtrip(self, tmp_path):
        m = DualProofManifest(
            synthetic_global_verdict="ACCEPT",
            fred_global_verdict="REJECT",
        )
        m.check_completeness()
        path = tmp_path / "manifest.json"
        m.save(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["synthetic_global_verdict"] == "ACCEPT"
        assert data["fred_global_verdict"] == "REJECT"


class TestBuildFromDisk:
    def test_build_from_synthetic_dir(self, tmp_path):
        tables = tmp_path / "tables"
        tables.mkdir()
        summary = {
            "protocol_verdict": "ACCEPT",
            "gate_passed": True,
            "support_level": "full_statistical_support",
            "n_statistical_passed": 145,
            "discrimination_metrics": {
                "confusion_matrix": {"TP": 48, "FN": 2, "FP": 3, "TN": 97},
                "sensitivity": 0.96,
                "specificity": 0.97,
            },
        }
        (tables / "validation_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        m = build_dual_proof_manifest(synthetic_dir=tmp_path)
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_gate_passed is True
        assert m.synthetic_n_statistical_passed == 145

    def test_build_handles_missing_dirs(self):
        m = build_dual_proof_manifest()
        m.check_completeness()
        assert m.dual_proof_status == "DUAL_PROOF_INCOMPLETE"


class TestFinalStatus:
    def test_complete_final_status(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
        )
        m.check_completeness()
        fs = build_final_status(m)
        assert fs["framework_status"] == "COMPLETE"
        assert fs["schema"] == "oric.final_status.v1"
        assert fs["n_empty"] == 0
        assert fs["n_inconsistencies"] == 0

    def test_incomplete_final_status(self):
        m = DualProofManifest()
        m.check_completeness()
        fs = build_final_status(m)
        assert fs["framework_status"] == "INCOMPLETE"
        assert fs["n_empty"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. integrity
# ═══════════════════════════════════════════════════════════════════════════

from oric.integrity import (
    check_run_integrity,
    check_dual_proof_integrity,
    integrity_gate,
)


class TestRunIntegrity:
    def test_valid_run(self, tmp_path):
        (tmp_path / "verdict.txt").write_text("ACCEPT\n")
        tables = tmp_path / "tables"
        tables.mkdir()
        (tables / "validation_summary.json").write_text(
            json.dumps({"protocol_verdict": "ACCEPT"}), encoding="utf-8"
        )
        result = check_run_integrity(tmp_path)
        assert result.passed

    def test_missing_verdict_txt(self, tmp_path):
        tables = tmp_path / "tables"
        tables.mkdir()
        result = check_run_integrity(tmp_path)
        assert not result.passed
        assert any("verdict.txt missing" in e for e in result.errors)

    def test_verdict_mismatch(self, tmp_path):
        (tmp_path / "verdict.txt").write_text("ACCEPT\n")
        tables = tmp_path / "tables"
        tables.mkdir()
        (tables / "validation_summary.json").write_text(
            json.dumps({"protocol_verdict": "REJECT"}), encoding="utf-8"
        )
        result = check_run_integrity(tmp_path)
        assert not result.passed

    def test_precheck_false_with_accept(self, tmp_path):
        (tmp_path / "verdict.txt").write_text("ACCEPT\n")
        tables = tmp_path / "tables"
        tables.mkdir()
        (tables / "validation_summary.json").write_text(
            json.dumps({
                "protocol_verdict": "ACCEPT",
                "precheck_passed": False,
            }),
            encoding="utf-8",
        )
        result = check_run_integrity(tmp_path)
        assert not result.passed
        assert any("precheck_passed=false" in e for e in result.errors)

    def test_accept_but_high_stable_detection(self, tmp_path):
        (tmp_path / "verdict.txt").write_text("ACCEPT\n")
        tables = tmp_path / "tables"
        tables.mkdir()
        (tables / "validation_summary.json").write_text(
            json.dumps({
                "protocol_verdict": "ACCEPT",
                "datasets": {
                    "test": {"metrics": {"detection_rate": 0.90}},
                    "stable": {"metrics": {"detection_rate": 0.80}},
                    "placebo": {"metrics": {"detection_rate": 0.10}},
                },
            }),
            encoding="utf-8",
        )
        result = check_run_integrity(tmp_path)
        assert not result.passed
        assert any("stable" in e for e in result.errors)


class TestDualProofIntegrity:
    def test_consistent_manifest_and_status(self, tmp_path):
        manifest = {
            "dual_proof_status": "DUAL_PROOF_COMPLETE",
            "empty_fields": [],
            "inconsistencies": [],
            "synthetic_global_verdict": "ACCEPT",
            "fred_global_verdict": "ACCEPT",
            "validation_verdict": "ACCEPT",
        }
        final = {
            "framework_status": "COMPLETE",
            "n_empty": 0,
            "synthetic_verdict": "ACCEPT",
            "real_data_verdict": "ACCEPT",
            "validation_verdict": "ACCEPT",
        }
        mp = tmp_path / "dual_proof_manifest.json"
        fp = tmp_path / "final_status.json"
        mp.write_text(json.dumps(manifest), encoding="utf-8")
        fp.write_text(json.dumps(final), encoding="utf-8")
        result = check_dual_proof_integrity(mp, fp)
        assert result.passed

    def test_complete_but_empty_fields(self, tmp_path):
        manifest = {
            "dual_proof_status": "DUAL_PROOF_COMPLETE",
            "empty_fields": ["synthetic.gate_passed"],
        }
        mp = tmp_path / "dual_proof_manifest.json"
        mp.write_text(json.dumps(manifest), encoding="utf-8")
        result = check_dual_proof_integrity(mp)
        assert not result.passed


class TestIntegrityGate:
    def test_all_pass(self, tmp_path):
        (tmp_path / "verdict.txt").write_text("ACCEPT\n")
        tables = tmp_path / "tables"
        tables.mkdir()
        (tables / "validation_summary.json").write_text(
            json.dumps({"protocol_verdict": "ACCEPT"}), encoding="utf-8"
        )
        checks = [check_run_integrity(tmp_path)]
        passed, errors = integrity_gate(checks)
        assert passed
        assert len(errors) == 0

    def test_failure_propagates(self, tmp_path):
        checks = [check_run_integrity(tmp_path)]  # empty dir
        passed, errors = integrity_gate(checks)
        assert not passed
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. placebo
# ═══════════════════════════════════════════════════════════════════════════

from oric.placebo import (
    make_cyclic_shift,
    make_temporal_permute,
    make_phase_randomize,
    make_proxy_remap,
    make_block_shuffle,
    generate_placebo_battery,
    evaluate_placebo_battery,
    ALL_STRATEGIES,
)


@pytest.fixture
def sample_df():
    rng = np.random.default_rng(42)
    n = 200
    return pd.DataFrame({
        "t": range(n),
        "O": rng.uniform(0.5, 0.9, n),
        "R": rng.uniform(0.5, 0.9, n),
        "I": rng.uniform(0.5, 0.9, n),
        "demand": rng.uniform(0.3, 0.8, n),
        "S": rng.uniform(0.1, 0.5, n),
    })


class TestPlaceboStrategies:
    def test_cyclic_shift_preserves_length(self, sample_df):
        out, spec = make_cyclic_shift(sample_df, seed=42)
        assert len(out) == len(sample_df)
        assert spec.strategy == "cyclic_shift"
        # Values should be the same, just shifted
        assert set(out["O"].round(6)) == set(sample_df["O"].round(6))

    def test_temporal_permute(self, sample_df):
        out, spec = make_temporal_permute(sample_df, seed=42)
        assert len(out) == len(sample_df)
        assert spec.strategy == "temporal_permute"
        # Same values but different order
        assert sorted(out["O"].round(6)) == sorted(sample_df["O"].round(6))
        # Order should differ
        assert not (out["O"].values == sample_df["O"].values).all()

    def test_phase_randomize(self, sample_df):
        out, spec = make_phase_randomize(sample_df, seed=42)
        assert len(out) == len(sample_df)
        assert spec.strategy == "phase_randomize"
        # Values should differ but mean should be similar
        assert abs(out["O"].mean() - sample_df["O"].mean()) < 0.1

    def test_proxy_remap(self, sample_df):
        out, spec = make_proxy_remap(sample_df, seed=42)
        assert len(out) == len(sample_df)
        assert spec.strategy == "proxy_remap"
        # Columns should be shuffled - at least one different
        all_same = all(
            (out[c].values == sample_df[c].values).all()
            for c in ["O", "R", "I", "demand", "S"]
        )
        assert not all_same

    def test_block_shuffle(self, sample_df):
        out, spec = make_block_shuffle(sample_df, seed=42)
        assert len(out) == len(sample_df)
        assert spec.strategy == "block_shuffle"

    def test_battery_generates_all_strategies(self, sample_df):
        results = generate_placebo_battery(sample_df, seed=42)
        assert len(results) == len(ALL_STRATEGIES)
        strategies_seen = {spec.strategy for _, spec in results}
        assert strategies_seen == set(ALL_STRATEGIES)

    def test_battery_deterministic(self, sample_df):
        r1 = generate_placebo_battery(sample_df, seed=42)
        r2 = generate_placebo_battery(sample_df, seed=42)
        for (df1, s1), (df2, s2) in zip(r1, r2):
            assert s1.strategy == s2.strategy
            pd.testing.assert_frame_equal(df1, df2)


class TestPlaceboBatteryEvaluation:
    def test_all_not_detected_passes(self):
        verdicts = [
            ("cyclic_shift", "NOT_DETECTED"),
            ("temporal_permute", "NOT_DETECTED"),
            ("phase_randomize", "NOT_DETECTED"),
            ("proxy_remap", "NOT_DETECTED"),
            ("block_shuffle", "NOT_DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.battery_passes
        assert result.detection_rate == 0.0

    def test_all_detected_fails(self):
        verdicts = [
            ("cyclic_shift", "DETECTED"),
            ("temporal_permute", "DETECTED"),
            ("phase_randomize", "DETECTED"),
            ("proxy_remap", "DETECTED"),
            ("block_shuffle", "DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert not result.battery_passes
        assert result.detection_rate == 1.0

    def test_one_detected_passes(self):
        verdicts = [
            ("cyclic_shift", "DETECTED"),
            ("temporal_permute", "NOT_DETECTED"),
            ("phase_randomize", "NOT_DETECTED"),
            ("proxy_remap", "NOT_DETECTED"),
            ("block_shuffle", "NOT_DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.battery_passes  # 1/5 = 0.20 <= 0.20

    def test_indeterminate_excluded(self):
        verdicts = [
            ("cyclic_shift", "INDETERMINATE"),
            ("temporal_permute", "NOT_DETECTED"),
            ("phase_randomize", "NOT_DETECTED"),
        ]
        result = evaluate_placebo_battery(verdicts, max_fp_rate=0.20)
        assert result.n_indeterminate == 1
        assert result.battery_passes


# ═══════════════════════════════════════════════════════════════════════════
# 4. decidability
# ═══════════════════════════════════════════════════════════════════════════

from oric.decidability import (
    compute_decidability,
    AdaptedPrechecks,
    check_precheck,
    build_decidability_report,
    DecidabilityMetrics,
)


class TestDecidabilityMetrics:
    def test_all_detected(self):
        runs = [{"verdict": "DETECTED"} for _ in range(10)]
        m = compute_decidability(runs, condition="test")
        assert m.n_decidable == 10
        assert m.detection_rate == 1.0
        assert m.indeterminate_rate == 0.0

    def test_all_indeterminate(self):
        runs = [{"verdict": "INDETERMINATE", "precheck_reason": "min_variance"} for _ in range(10)]
        m = compute_decidability(runs, condition="stable")
        assert m.n_decidable == 0
        assert m.indeterminate_rate == 1.0
        assert m.top_indeterminate_reason == "min_variance"

    def test_mixed(self):
        runs = [
            {"verdict": "DETECTED"},
            {"verdict": "NOT_DETECTED"},
            {"verdict": "INDETERMINATE", "precheck_reason": "too_short"},
            {"verdict": "NOT_DETECTED"},
        ]
        m = compute_decidability(runs, condition="stable")
        assert m.n_total == 4
        assert m.n_decidable == 3
        assert m.n_indeterminate == 1
        assert m.detection_rate == pytest.approx(1 / 3)
        assert m.non_detection_rate == pytest.approx(2 / 3)

    def test_reason_taxonomy(self):
        runs = [
            {"verdict": "INDETERMINATE", "precheck_reason": "min_variance"},
            {"verdict": "INDETERMINATE", "precheck_reason": "min_variance"},
            {"verdict": "INDETERMINATE", "precheck_reason": "min_unique"},
            {"verdict": "DETECTED"},
        ]
        m = compute_decidability(runs)
        assert m.indeterminate_reasons["min_variance"] == 2
        assert m.indeterminate_reasons["min_unique"] == 1
        assert m.top_indeterminate_reason == "min_variance"


class TestAdaptedPrechecks:
    def test_stable_relaxed_thresholds(self):
        pc = AdaptedPrechecks.for_regime("stable", series_length=200)
        assert pc.min_unique_values_C == 3  # relaxed from 5
        assert pc.min_variance_C < 1e-10

    def test_test_default_thresholds(self):
        pc = AdaptedPrechecks.for_regime("test")
        assert pc.min_unique_values_C == 5
        assert pc.min_variance_C == 1e-10

    def test_check_passes(self):
        c_pre = np.random.default_rng(42).normal(0, 1, 100)
        c_post = np.random.default_rng(43).normal(1, 1, 100)
        pc = AdaptedPrechecks()
        passed, reason = check_precheck(c_pre, c_post, pc)
        assert passed
        assert reason is None

    def test_check_fails_too_short(self):
        c_pre = np.array([1.0, 2.0])
        c_post = np.array([3.0, 4.0])
        pc = AdaptedPrechecks(min_points_per_segment=10)
        passed, reason = check_precheck(c_pre, c_post, pc)
        assert not passed
        assert "min_points" in reason

    def test_check_fails_low_unique(self):
        c_pre = np.ones(100)
        c_post = np.ones(100)
        pc = AdaptedPrechecks(min_unique_values_C=3)
        passed, reason = check_precheck(c_pre, c_post, pc)
        assert not passed
        assert "min_unique" in reason


class TestDecidabilityReport:
    def test_report_structure(self):
        test_m = DecidabilityMetrics(condition="test", n_total=50, n_decidable=48,
                                     n_detected=45, n_not_detected=3, n_indeterminate=2)
        test_m.decidable_fraction = 0.96
        test_m.detection_rate = 45 / 48
        test_m.non_detection_rate = 3 / 48
        test_m.indeterminate_rate = 2 / 50

        stable_m = DecidabilityMetrics(condition="stable", n_total=50, n_decidable=35,
                                       n_detected=2, n_not_detected=33, n_indeterminate=15)
        stable_m.decidable_fraction = 0.70
        stable_m.detection_rate = 2 / 35
        stable_m.non_detection_rate = 33 / 35
        stable_m.indeterminate_rate = 15 / 50

        placebo_m = DecidabilityMetrics(condition="placebo", n_total=50, n_decidable=40,
                                        n_detected=5, n_not_detected=35, n_indeterminate=10)
        placebo_m.decidable_fraction = 0.80
        placebo_m.detection_rate = 5 / 40
        placebo_m.non_detection_rate = 35 / 40
        placebo_m.indeterminate_rate = 10 / 50

        report = build_decidability_report(test_m, stable_m, placebo_m)
        assert "overall" in report
        assert "per_condition" in report
        assert report["stable_decides_non_detection"] is True

    def test_low_stable_decidability_warning(self):
        test_m = DecidabilityMetrics(condition="test", n_total=10, n_decidable=9)
        test_m.decidable_fraction = 0.90
        stable_m = DecidabilityMetrics(condition="stable", n_total=10, n_decidable=3)
        stable_m.decidable_fraction = 0.30
        placebo_m = DecidabilityMetrics(condition="placebo", n_total=10, n_decidable=8)
        placebo_m.decidable_fraction = 0.80

        report = build_decidability_report(test_m, stable_m, placebo_m)
        assert any("stable decidability low" in r for r in report["recommendations"])


# ═══════════════════════════════════════════════════════════════════════════
# 5. proof_levels
# ═══════════════════════════════════════════════════════════════════════════

from oric.proof_levels import (
    classify_evidence_level,
    build_proof_level_summary,
    DatasetEvidence,
)


class TestProofLevels:
    def test_level_a_classification(self):
        ev = classify_evidence_level(
            dataset_id="fred_monthly",
            n_rows=480,
            verdict="ACCEPT",
            precheck_passed=True,
            causal_tests_available=True,
            sensitivity=0.95,
            category="economic",
        )
        assert ev.level == "A"

    def test_level_b_short_series(self):
        ev = classify_evidence_level(
            dataset_id="traffic_pilot",
            n_rows=50,
            verdict="INDETERMINATE",
            precheck_passed=False,
            causal_tests_available=False,
            category="transport",
        )
        assert ev.level == "B"
        assert "series_too_short" in ev.reason_for_level
        assert ev.computation_coherent is True

    def test_level_b_precheck_failed(self):
        ev = classify_evidence_level(
            dataset_id="meteo_pilot",
            n_rows=300,
            verdict="INDETERMINATE",
            precheck_passed=False,
            causal_tests_available=False,
        )
        assert ev.level == "B"
        assert "precheck_failed" in ev.reason_for_level


class TestProofLevelSummary:
    def test_summary_with_mixed_levels(self):
        evs = [
            classify_evidence_level("fred", 480, "ACCEPT", True, True, 0.95),
            classify_evidence_level("synthetic", 2600, "ACCEPT", True, True, 0.98),
            classify_evidence_level("traffic", 50, "INDETERMINATE", False, False),
            classify_evidence_level("meteo", 80, "INDETERMINATE", False, False),
        ]
        summary = build_proof_level_summary(evs)
        assert summary.n_level_a == 2
        assert summary.n_level_b == 2
        assert summary.level_a_all_accept is True
        assert summary.level_a_verdict == "ACCEPT"

    def test_no_level_a(self):
        evs = [
            classify_evidence_level("traffic", 50, "INDETERMINATE", False, False),
        ]
        summary = build_proof_level_summary(evs)
        assert summary.n_level_a == 0
        assert summary.level_a_verdict == "NO_CANONICAL_DATA"


# ═══════════════════════════════════════════════════════════════════════════
# 6. proof_package
# ═══════════════════════════════════════════════════════════════════════════

from oric.proof_package import build_proof_package, ProofPackage


class TestProofPackage:
    def test_minimal_package(self):
        m = DualProofManifest()
        m.check_completeness()
        pkg = build_proof_package(m)
        assert pkg.overall_verdict == "INCOMPLETE"
        assert pkg.bloc_verdicts["bloc1_contractual"] == "FAIL"

    def test_complete_package(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
        )
        m.check_completeness()

        dm = {
            "confusion_matrix": {"TP": 48, "FN": 2, "FP": 3, "TN": 97},
            "sensitivity": 0.96,
            "specificity": 0.97,
            "fisher_p_value": 1e-30,
            "indeterminate_rate_by_condition": {
                "test": 0.04, "stable": 0.10, "placebo": 0.06,
            },
        }

        pkg = build_proof_package(
            manifest=m,
            discrimination_metrics=dm,
            window_stability={"rows": [
                {"dataset": "test", "verdict": "ACCEPT"},
                {"dataset": "test", "verdict": "ACCEPT"},
            ]},
            subsample_stability={"stability": 0.95},
        )
        assert pkg.bloc1_contractual.manifest_complete is True
        assert pkg.bloc2_discriminant.discrimination_passes is True
        assert pkg.bloc3_robustness.robustness_passes is True
        assert pkg.overall_verdict == "ACCEPT"

    def test_serialization(self, tmp_path):
        m = DualProofManifest()
        m.check_completeness()
        pkg = build_proof_package(m)
        path = tmp_path / "proof_package.json"
        pkg.save(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == "oric.proof_package.v1"
        assert "bloc1_contractual" in data

    def test_verdict_flip_detection(self):
        m = DualProofManifest()
        m.check_completeness()
        pkg = build_proof_package(
            m,
            window_stability={"rows": [
                {"dataset": "test", "verdict": "ACCEPT"},
                {"dataset": "test", "verdict": "REJECT"},
            ]},
        )
        assert pkg.bloc3_robustness.verdict_flip_detected is True
        assert pkg.bloc3_robustness.robustness_passes is False


# ═══════════════════════════════════════════════════════════════════════════
# 7. CI gate: ACCEPT implies manifest is complete
# ═══════════════════════════════════════════════════════════════════════════

class TestCIGate:
    """Tests that would fail CI if the framework produces contradictory state."""

    def test_accept_requires_no_empty_fields(self):
        """If global_verdict=ACCEPT, dual_proof_manifest must have no empty fields."""
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
        )
        m.check_completeness()
        fs = build_final_status(m)

        if fs["framework_status"] == "COMPLETE":
            assert fs["n_empty"] == 0, (
                f"COMPLETE status but {fs['n_empty']} empty fields: "
                f"{m.empty_fields}"
            )
            assert fs["n_inconsistencies"] == 0, (
                f"COMPLETE status but {fs['n_inconsistencies']} inconsistencies"
            )

    def test_accept_requires_discrimination(self):
        """ACCEPT package must have sensitivity >= 0.80 and specificity >= 0.80."""
        dm = {
            "sensitivity": 0.60,
            "specificity": 0.90,
            "fisher_p_value": 0.001,
            "confusion_matrix": {"TP": 30, "FN": 20, "FP": 5, "TN": 95},
            "indeterminate_rate_by_condition": {"test": 0, "stable": 0, "placebo": 0},
        }
        m = DualProofManifest()
        m.check_completeness()
        pkg = build_proof_package(m, discrimination_metrics=dm)
        # Even with metrics, sensitivity < 0.80 means discrimination fails
        assert pkg.bloc2_discriminant.discrimination_passes is False
