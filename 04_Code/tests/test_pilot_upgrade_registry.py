"""test_pilot_upgrade_registry.py — Tests that the pilot registry reflects
the actual state of upgrade results.

Ensures that:
- The registry version has been bumped
- Upgrade candidates are properly tracked
- Registry is consistent with upgrade reports
- Registry is consistent with frozen corpus
- Level transitions follow protocol rules
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
RESULTS = ROOT / "05_Results"
PILOTS = RESULTS / "pilots"
UPGRADE_DIR = PILOTS / "power_upgrade"

LEVEL_C_PILOTS = [
    "sector_cosmo.pilot_pantheon_sn",
    "sector_bio.pilot_pbdb_marine",
    "sector_ai_tech.pilot_llm_scaling",
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Registry structure
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryStructure:
    """Validate pilot_generalization_registry.json v2."""

    @pytest.fixture
    def registry(self):
        path = PILOTS / "pilot_generalization_registry.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_schema(self, registry):
        assert registry["schema"] == "oric.pilot_generalization_registry.v1"

    def test_version_2(self, registry):
        parts = registry["version"].split(".")
        assert int(parts[0]) >= 2, "Registry must be version 2.0.0+"

    def test_seven_pilots(self, registry):
        assert len(registry["pilots"]) == 7

    def test_upgrade_summary_present(self, registry):
        assert "upgrade_summary" in registry
        us = registry["upgrade_summary"]
        assert "total_upgrade_candidates" in us
        assert "anti_gaming_note" in us

    def test_upgrade_candidates_count(self, registry):
        candidates = [
            p for p in registry["pilots"]
            if p.get("upgrade_status") == "upgrade_candidate"
        ]
        assert len(candidates) == 3

    def test_level_b_pilots_have_no_upgrade(self, registry):
        for p in registry["pilots"]:
            if p["proof_level"] == "B":
                assert p.get("upgrade_status") is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. Upgrade candidates consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestUpgradeCandidatesConsistency:
    """Ensure upgrade candidates in registry match actual reports."""

    @pytest.fixture
    def registry(self):
        return json.loads(
            (PILOTS / "pilot_generalization_registry.json").read_text()
        )

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_candidate_has_upgrade_report(self, registry, pilot_id):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        assert pilot.get("upgrade_status") == "upgrade_candidate"
        assert "upgrade_report" in pilot
        report = pilot["upgrade_report"]
        assert report["n_after"] > report["n_before"]
        assert report["homogeneity_passed"] is True

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_level_remains_c_until_validated(self, registry, pilot_id):
        """Level C pilots must stay at C even if upgrade_candidate."""
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        assert pilot["proof_level"] == "C", (
            f"{pilot_id} should remain Level C until full validation"
        )

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_upgrade_report_matches_results(self, registry, pilot_id):
        """Registry upgrade data must match the actual report file."""
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        report_path = UPGRADE_DIR / pilot_id.replace(".", "/") / "power_upgrade_report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert pilot["upgrade_report"]["n_before"] == report["n_before"]
        assert pilot["upgrade_report"]["n_after"] == report["n_after"]
        assert pilot["upgrade_report"]["homogeneity_passed"] == report["homogeneity_passed"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. Registry consistent with frozen corpus
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryCorpusConsistency:
    """Registry must be consistent with FROZEN_PILOT_CORPUS.json."""

    def test_same_pilot_ids(self):
        registry = json.loads(
            (PILOTS / "pilot_generalization_registry.json").read_text()
        )
        corpus = json.loads(
            (CONTRACTS / "FROZEN_PILOT_CORPUS.json").read_text()
        )
        reg_ids = {p["pilot_id"] for p in registry["pilots"]}
        corp_ids = {p["pilot_id"] for p in corpus["pilots"]}
        assert reg_ids == corp_ids

    def test_verdicts_match(self):
        registry = json.loads(
            (PILOTS / "pilot_generalization_registry.json").read_text()
        )
        corpus = json.loads(
            (CONTRACTS / "FROZEN_PILOT_CORPUS.json").read_text()
        )
        corp_verdicts = {p["pilot_id"]: p["oric_verdict"] for p in corpus["pilots"]}
        for p in registry["pilots"]:
            assert p["oric_verdict"] == corp_verdicts[p["pilot_id"]], (
                f"Verdict mismatch for {p['pilot_id']}: "
                f"registry={p['oric_verdict']}, corpus={corp_verdicts[p['pilot_id']]}"
            )

    def test_proof_levels_match(self):
        registry = json.loads(
            (PILOTS / "pilot_generalization_registry.json").read_text()
        )
        corpus = json.loads(
            (CONTRACTS / "FROZEN_PILOT_CORPUS.json").read_text()
        )
        corp_levels = {p["pilot_id"]: p["proof_level"] for p in corpus["pilots"]}
        for p in registry["pilots"]:
            assert p["proof_level"] == corp_levels[p["pilot_id"]], (
                f"Level mismatch for {p['pilot_id']}: "
                f"registry={p['proof_level']}, corpus={corp_levels[p['pilot_id']]}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Benchmark summary consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestBenchmarkSummaryConsistency:
    """Validate pilot_benchmark_summary.json upgrade section."""

    @pytest.fixture
    def summary(self):
        path = RESULTS / "pilot_benchmark_summary.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_upgrade_candidates_section(self, summary):
        assert "upgrade_candidates" in summary
        assert summary["upgrade_candidates"]["total"] == 3

    def test_upgrade_pilots_listed(self, summary):
        ids = {p["pilot_id"] for p in summary["upgrade_candidates"]["pilots"]}
        assert ids == set(LEVEL_C_PILOTS)

    def test_all_homogeneity_passed(self, summary):
        for p in summary["upgrade_candidates"]["pilots"]:
            assert p["homogeneity_passed"] is True

    def test_all_level_b_candidate(self, summary):
        for p in summary["upgrade_candidates"]["pilots"]:
            assert p["level_after"] == "B_candidate"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Cross-references valid
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossReferences:
    """Validate that registry cross-references point to existing files."""

    def test_all_references_exist(self):
        registry = json.loads(
            (PILOTS / "pilot_generalization_registry.json").read_text()
        )
        refs = registry["cross_references"]
        for key, path_str in refs.items():
            path = ROOT / path_str
            assert path.exists(), f"Cross-reference {key} -> {path_str} missing"
