"""test_pilot_generalization.py — Tests for proof levels (A/B/C), power classes,
generalization matrix, and pilot benchmark contracts.

Covers:
- Three-level evidence classification (A, B, C)
- Power class assignment (adequate, borderline, underpowered)
- Generalization matrix contract integrity
- Pilot benchmark summary consistency
- Power upgrade protocol completeness
- Showcase pilot configuration
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
RESULTS = ROOT / "05_Results"


# ── Framework imports ──────────────────────────────────────────────────────

from oric.proof_levels import (
    classify_evidence_level,
    classify_power,
    build_proof_level_summary,
    DatasetEvidence,
    ProofLevelSummary,
    MIN_ROWS_CANONICAL,
    MIN_ROWS_CONCLUSIVE,
    MIN_POINTS_PER_SEGMENT,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Power class tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPowerClass:
    """Test power classification logic."""

    def test_adequate(self):
        assert classify_power(200, True) == "adequate"
        assert classify_power(500, True) == "adequate"
        assert classify_power(1000, True) == "adequate"

    def test_borderline(self):
        assert classify_power(60, True) == "borderline"
        assert classify_power(100, True) == "borderline"
        assert classify_power(199, True) == "borderline"

    def test_underpowered(self):
        assert classify_power(59, True) == "underpowered"
        assert classify_power(30, True) == "underpowered"
        assert classify_power(10, True) == "underpowered"

    def test_segment_failure_forces_underpowered(self):
        """Even 200+ rows → underpowered if min_points_per_segment not met."""
        assert classify_power(300, False) == "underpowered"

    def test_thresholds_match_constants(self):
        assert MIN_ROWS_CANONICAL == 200
        assert MIN_ROWS_CONCLUSIVE == 60
        assert MIN_POINTS_PER_SEGMENT == 60


# ═══════════════════════════════════════════════════════════════════════════
# 2. Three-level classification tests
# ═══════════════════════════════════════════════════════════════════════════

class TestThreeLevelClassification:
    """Test Level A / B / C classification."""

    def test_level_a_canonical(self):
        ev = classify_evidence_level(
            dataset_id="synthetic",
            n_rows=500,
            verdict="ACCEPT",
            precheck_passed=True,
            causal_tests_available=True,
            sensitivity=1.0,
            specificity=1.0,
        )
        assert ev.level == "A"
        assert ev.power_class == "adequate"
        assert ev.overinterpretation_risk == "very_low"

    def test_level_b_conclusive_pilot_adequate(self):
        """EEG Bonn: 500 rows, ACCEPT, adequate power."""
        ev = classify_evidence_level(
            dataset_id="sector_neuro.pilot_eeg_bonn",
            n_rows=500,
            verdict="ACCEPT",
            precheck_passed=True,
            causal_tests_available=True,
            category="neuro",
        )
        # n_rows >= 200 and precheck + causal → Level A actually
        assert ev.level == "A"
        assert ev.power_class == "adequate"

    def test_level_b_conclusive_pilot_borderline(self):
        """BTC: 141 rows, ACCEPT, borderline power."""
        ev = classify_evidence_level(
            dataset_id="sector_finance.pilot_btc",
            n_rows=141,
            verdict="ACCEPT",
            precheck_passed=True,
            causal_tests_available=True,
            category="finance",
        )
        assert ev.level == "B"
        assert ev.power_class == "borderline"
        assert ev.overinterpretation_risk == "low"
        assert ev.computation_coherent is True
        assert ev.mapping_feasible is True

    def test_level_c_underpowered(self):
        """LLM scaling: 60 rows, INDETERMINATE, underpowered."""
        ev = classify_evidence_level(
            dataset_id="sector_ai_tech.pilot_llm_scaling",
            n_rows=60,
            verdict="INDETERMINATE",
            precheck_passed=False,
            causal_tests_available=False,
            min_points_per_segment_met=False,
            signal_plausible=True,
            power_upgrade_path="Extend with MLPerf, MMLU benchmarks",
            category="ai_tech",
        )
        assert ev.level == "C"
        assert ev.power_class == "underpowered"
        assert ev.overinterpretation_risk == "high"
        assert ev.signal_plausible is True
        assert "MLPerf" in ev.power_upgrade_path
        assert len(ev.limitation_notes) > 0

    def test_level_c_borderline_indeterminate(self):
        """Pantheon SN: 100 rows, INDETERMINATE, borderline."""
        ev = classify_evidence_level(
            dataset_id="sector_cosmo.pilot_pantheon_sn",
            n_rows=100,
            verdict="INDETERMINATE",
            precheck_passed=False,
            causal_tests_available=True,
            category="cosmo",
        )
        assert ev.level == "C"
        assert ev.power_class == "borderline"
        assert ev.overinterpretation_risk == "medium"

    def test_level_b_reject_is_valid(self):
        """REJECT verdict at Level B is valid — it's decidable."""
        ev = classify_evidence_level(
            dataset_id="test_reject",
            n_rows=150,
            verdict="REJECT",
            precheck_passed=True,
            causal_tests_available=True,
        )
        assert ev.level == "B"
        assert ev.verdict == "REJECT"

    def test_level_a_requires_200_rows(self):
        ev = classify_evidence_level(
            dataset_id="test",
            n_rows=199,
            verdict="ACCEPT",
            precheck_passed=True,
            causal_tests_available=True,
        )
        assert ev.level == "B"  # Not A: too short

    def test_level_c_with_decidable_fraction(self):
        ev = classify_evidence_level(
            dataset_id="test",
            n_rows=50,
            verdict="INDETERMINATE",
            precheck_passed=False,
            causal_tests_available=False,
            decidable_fraction=0.30,
        )
        assert ev.level == "C"
        assert any("Decidable fraction" in n for n in ev.limitation_notes)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Proof level summary tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProofLevelSummary:
    """Test aggregation of evidence across datasets."""

    def _make_evidence(self, level, verdict, power_class):
        ev = DatasetEvidence()
        ev.level = level
        ev.verdict = verdict
        ev.power_class = power_class
        return ev

    def test_summary_counts(self):
        evs = [
            self._make_evidence("A", "ACCEPT", "adequate"),
            self._make_evidence("B", "ACCEPT", "borderline"),
            self._make_evidence("B", "ACCEPT", "adequate"),
            self._make_evidence("C", "INDETERMINATE", "underpowered"),
        ]
        s = build_proof_level_summary(evs)
        assert s.n_level_a == 1
        assert s.n_level_b == 2
        assert s.n_level_c == 1
        assert s.n_adequate == 2
        assert s.n_borderline == 1
        assert s.n_underpowered == 1

    def test_summary_level_a_all_accept(self):
        evs = [
            self._make_evidence("A", "ACCEPT", "adequate"),
            self._make_evidence("A", "ACCEPT", "adequate"),
        ]
        s = build_proof_level_summary(evs)
        assert s.level_a_all_accept is True
        assert s.level_a_verdict == "ACCEPT"

    def test_summary_no_canonical_data(self):
        evs = [self._make_evidence("B", "ACCEPT", "borderline")]
        s = build_proof_level_summary(evs)
        assert s.level_a_verdict == "NO_CANONICAL_DATA"

    def test_summary_to_dict_has_level_c(self):
        evs = [self._make_evidence("C", "INDETERMINATE", "underpowered")]
        s = build_proof_level_summary(evs)
        d = s.to_dict()
        assert "n_level_c" in d
        assert d["n_level_c"] == 1
        assert "power_distribution" in d
        assert d["power_distribution"]["underpowered"] == 1

    def test_summary_save_roundtrip(self, tmp_path):
        evs = [
            self._make_evidence("A", "ACCEPT", "adequate"),
            self._make_evidence("C", "INDETERMINATE", "underpowered"),
        ]
        s = build_proof_level_summary(evs)
        path = tmp_path / "summary.json"
        s.save(path)
        loaded = json.loads(path.read_text())
        assert loaded["n_level_a"] == 1
        assert loaded["n_level_c"] == 1
        assert loaded["power_distribution"]["adequate"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. Contract integrity tests
# ═══════════════════════════════════════════════════════════════════════════

class TestGeneralizationContract:
    """Validate PILOT_GENERALIZATION.json structure and consistency."""

    @pytest.fixture
    def contract(self):
        path = CONTRACTS / "PILOT_GENERALIZATION.json"
        assert path.exists(), f"Contract not found: {path}"
        return json.loads(path.read_text())

    def test_schema_version(self, contract):
        assert contract["schema"] == "oric.pilot_generalization.v1"

    def test_three_proof_levels(self, contract):
        levels = contract["proof_levels"]
        assert set(levels.keys()) == {"A", "B", "C"}

    def test_three_power_classes(self, contract):
        classes = contract["power_classes"]
        assert set(classes.keys()) == {"adequate", "borderline", "underpowered"}

    def test_matrix_has_7_pilots(self, contract):
        assert len(contract["generalization_matrix"]) == 7

    def test_matrix_required_fields(self, contract):
        required = {
            "pilot_id", "domain", "sector", "series_length",
            "signal_expected", "oric_verdict", "proof_level", "power_class",
        }
        for pilot in contract["generalization_matrix"]:
            missing = required - set(pilot.keys())
            assert not missing, f"{pilot['pilot_id']} missing: {missing}"

    def test_level_b_are_decidable(self, contract):
        for p in contract["generalization_matrix"]:
            if p["proof_level"] == "B":
                assert p["oric_verdict"] in ("ACCEPT", "REJECT"), (
                    f"{p['pilot_id']} Level B must be decidable"
                )

    def test_all_pilots_are_level_b(self, contract):
        for p in contract["generalization_matrix"]:
            assert p["proof_level"] == "B", f"{p['pilot_id']} should be Level B"

    def test_summary_counts_consistent(self, contract):
        matrix = contract["generalization_matrix"]
        summary = contract["summary"]
        assert summary["total_pilots"] == len(matrix)
        assert summary["level_B_accept"] == sum(
            1 for p in matrix if p["oric_verdict"] == "ACCEPT"
        )
        assert summary.get("level_B_reject", 0) == sum(
            1 for p in matrix if p["oric_verdict"] == "REJECT"
        )
        assert summary.get("level_C_indeterminate", 0) == 0


class TestPowerUpgradeProtocol:
    """Validate POWER_UPGRADE_PROTOCOL.json."""

    @pytest.fixture
    def protocol(self):
        path = CONTRACTS / "POWER_UPGRADE_PROTOCOL.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_schema(self, protocol):
        assert protocol["schema"] == "oric.power_upgrade_protocol.v1"

    def test_three_pilots(self, protocol):
        assert len(protocol["pilots"]) == 3

    def test_all_pilots_have_upgrade_plan(self, protocol):
        for p in protocol["pilots"]:
            plan = p["upgrade_plan"]
            assert plan["target_length"] >= 120
            assert plan["target_pre_segment"] >= 60
            assert plan["target_post_segment"] >= 60
            assert len(plan["segmentation_candidates"]) >= 2
            assert len(plan["data_sources"]) >= 2

    def test_all_pilots_have_success_criteria(self, protocol):
        for p in protocol["pilots"]:
            sc = p["success_criteria"]
            assert sc["min_total_points"] >= 120
            assert sc["min_points_per_segment"] >= 60
            assert sc["precheck_must_pass"] is True
            assert sc["verdict_must_be_decidable"] is True

    def test_upgrade_protocol_pilots_are_in_matrix(self):
        gen = json.loads(
            (CONTRACTS / "PILOT_GENERALIZATION.json").read_text()
        )
        matrix_ids = {p["pilot_id"] for p in gen["generalization_matrix"]}
        proto = json.loads(
            (CONTRACTS / "POWER_UPGRADE_PROTOCOL.json").read_text()
        )
        upgrade_ids = {p["pilot_id"] for p in proto["pilots"]}
        assert upgrade_ids.issubset(matrix_ids), (
            f"Upgrade pilots not in matrix: {upgrade_ids - matrix_ids}"
        )


class TestBenchmarkSummary:
    """Validate pilot_benchmark_summary.json."""

    @pytest.fixture
    def summary(self):
        path = RESULTS / "pilot_benchmark_summary.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_schema(self, summary):
        assert summary["schema"] == "oric.pilot_benchmark.v1"

    def test_total_pilots(self, summary):
        assert summary["total_pilots"] == 7

    def test_verdict_sum(self, summary):
        v = summary["verdicts"]
        assert v["ACCEPT"] + v["INDETERMINATE"] + v["REJECT"] == 7

    def test_level_sum(self, summary):
        levels = summary["proof_levels"]
        total = sum(lvl["count"] for lvl in levels.values())
        assert total == 7

    def test_power_sum(self, summary):
        power_dist = summary["power_distribution"]
        total = sum(p["count"] for p in power_dist.values())
        assert total == 7

    def test_showcase_pilots_exist(self, summary):
        assert summary["showcase_pilots"]["primary"]["pilot_id"]
        assert summary["showcase_pilots"]["secondary"]["pilot_id"]

    def test_prudent_reading(self, summary):
        pr = summary["prudent_reading"]
        assert len(pr["exploitable_positives"]) == 5
        assert len(pr["confirmed_negatives"]) == 2


class TestShowcasePilots:
    """Validate SHOWCASE_PILOTS.json."""

    @pytest.fixture
    def showcase(self):
        path = CONTRACTS / "SHOWCASE_PILOTS.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_schema(self, showcase):
        assert showcase["schema"] == "oric.showcase_pilots.v1"

    def test_primary_is_eeg(self, showcase):
        assert showcase["primary"]["pilot_id"] == "sector_neuro.pilot_eeg_bonn"
        assert showcase["primary"]["proof_level"] == "B"

    def test_secondary_is_btc(self, showcase):
        assert showcase["secondary"]["pilot_id"] == "sector_finance.pilot_btc"
        assert showcase["secondary"]["proof_level"] == "B"

    def test_data_paths_exist(self, showcase):
        for key in ["primary", "secondary"]:
            dp = ROOT / showcase[key]["data_path"]
            assert dp.exists(), f"Showcase data path missing: {dp}"

    def test_both_are_level_b(self, showcase):
        for key in ["primary", "secondary"]:
            assert showcase[key]["proof_level"] == "B"
            assert showcase[key]["verdict"] == "ACCEPT"
