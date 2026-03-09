"""test_pilot_upgrade_registry.py — Tests that the pilot registry reflects
the actual state of upgrade results.

Ensures that:
- The registry version has been bumped to v3
- All 3 upgraded pilots have decidable verdicts
- Registry is consistent with upgrade reports and validation summaries
- Registry is consistent with frozen corpus
- All pilots are now Level B
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
RESULTS = ROOT / "05_Results"
PILOTS = RESULTS / "pilots"
UPGRADE_DIR = PILOTS / "power_upgrade"
VALIDATION_DIR = RESULTS / "real_validation"

UPGRADED_PILOTS = [
    "sector_cosmo.pilot_pantheon_sn",
    "sector_bio.pilot_pbdb_marine",
    "sector_ai_tech.pilot_llm_scaling",
]

EXPECTED_VERDICTS = {
    "sector_cosmo.pilot_pantheon_sn": "ACCEPT",
    "sector_bio.pilot_pbdb_marine": "REJECT",
    "sector_ai_tech.pilot_llm_scaling": "REJECT",
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Registry structure
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryStructure:
    """Validate pilot_generalization_registry.json v3."""

    @pytest.fixture
    def registry(self):
        path = PILOTS / "pilot_generalization_registry.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_schema(self, registry):
        assert registry["schema"] == "oric.pilot_generalization_registry.v1"

    def test_version_3(self, registry):
        parts = registry["version"].split(".")
        assert int(parts[0]) >= 3, "Registry must be version 3.0.0+"

    def test_seven_pilots(self, registry):
        assert len(registry["pilots"]) == 7

    def test_all_level_b(self, registry):
        for p in registry["pilots"]:
            assert p["proof_level"] == "B"

    def test_no_indeterminate(self, registry):
        for p in registry["pilots"]:
            assert p["oric_verdict"] != "INDETERMINATE"

    def test_upgrade_summary_present(self, registry):
        assert "upgrade_summary" in registry
        us = registry["upgrade_summary"]
        assert us["validation_pipeline_completed"] is True
        assert "anti_gaming_note" in us

    def test_upgraded_count(self, registry):
        upgraded = [
            p for p in registry["pilots"]
            if p.get("upgrade_status") == "upgraded"
        ]
        assert len(upgraded) == 3

    def test_summary_counts(self, registry):
        s = registry["summary"]
        assert s["by_verdict"]["ACCEPT"] == 5
        assert s["by_verdict"]["REJECT"] == 2
        assert s["by_verdict"]["INDETERMINATE"] == 0
        assert s["by_level"]["B"] == 7
        assert s["by_level"].get("C", 0) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Upgraded pilots have complete validation data
# ═══════════════════════════════════════════════════════════════════════════

class TestUpgradedPilotsValidation:
    """Ensure upgraded pilots have full validation reports."""

    @pytest.fixture
    def registry(self):
        return json.loads(
            (PILOTS / "pilot_generalization_registry.json").read_text()
        )

    @pytest.mark.parametrize("pilot_id", UPGRADED_PILOTS)
    def test_has_upgrade_report(self, registry, pilot_id):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        assert pilot.get("upgrade_status") == "upgraded"
        assert "upgrade_report" in pilot
        report = pilot["upgrade_report"]
        assert report["n_after"] > report["n_before"]
        assert report["homogeneity_passed"] is True
        assert report["level_after"] == "B"

    @pytest.mark.parametrize("pilot_id", UPGRADED_PILOTS)
    def test_validation_verdict_correct(self, registry, pilot_id):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        report = pilot["upgrade_report"]
        assert report["validation_verdict"] == EXPECTED_VERDICTS[pilot_id]
        assert report["validation_decidable_runs"] == 45
        assert report["validation_indeterminate"] == 0

    @pytest.mark.parametrize("pilot_id", UPGRADED_PILOTS)
    def test_oric_verdict_matches(self, registry, pilot_id):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        assert pilot["oric_verdict"] == EXPECTED_VERDICTS[pilot_id]

    @pytest.mark.parametrize("pilot_id", UPGRADED_PILOTS)
    def test_validation_c2_c3_passed(self, registry, pilot_id):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == pilot_id)
        report = pilot["upgrade_report"]
        assert report["validation_c2"] is True
        assert report["validation_c3"] is True

    def test_pantheon_sn_c1_passed(self, registry):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == "sector_cosmo.pilot_pantheon_sn")
        assert pilot["upgrade_report"]["validation_c1"] is True
        assert pilot["upgrade_report"]["detection_rate"] == 1.0

    def test_pbdb_marine_c1_failed(self, registry):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == "sector_bio.pilot_pbdb_marine")
        assert pilot["upgrade_report"]["validation_c1"] is False
        assert pilot["upgrade_report"]["failure_mode"] == "no_detection"

    def test_llm_scaling_c1_failed(self, registry):
        pilot = next(p for p in registry["pilots"] if p["pilot_id"] == "sector_ai_tech.pilot_llm_scaling")
        assert pilot["upgrade_report"]["validation_c1"] is False
        assert pilot["upgrade_report"]["failure_mode"] == "no_detection"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Validation summary files exist
# ═══════════════════════════════════════════════════════════════════════════

class TestValidationSummaryFiles:
    """Ensure validation output files exist for each upgraded pilot."""

    VALIDATION_DIRS = {
        "sector_cosmo.pilot_pantheon_sn": "pilot_pantheon_sn_densified",
        "sector_bio.pilot_pbdb_marine": "pilot_pbdb_marine_densified",
        "sector_ai_tech.pilot_llm_scaling": "pilot_llm_scaling_densified",
    }

    @pytest.mark.parametrize("pilot_id", UPGRADED_PILOTS)
    def test_validation_summary_exists(self, pilot_id):
        dirname = self.VALIDATION_DIRS[pilot_id]
        path = VALIDATION_DIR / dirname / "real_densified" / "tables" / "validation_summary.json"
        assert path.exists(), f"Missing validation summary: {path}"

    @pytest.mark.parametrize("pilot_id", UPGRADED_PILOTS)
    def test_validation_verdict_matches(self, pilot_id):
        dirname = self.VALIDATION_DIRS[pilot_id]
        path = VALIDATION_DIR / dirname / "real_densified" / "tables" / "validation_summary.json"
        summary = json.loads(path.read_text())
        assert summary["protocol_verdict"] == EXPECTED_VERDICTS[pilot_id]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Registry consistent with frozen corpus
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryCorpusConsistency:
    """Registry must be consistent with FROZEN_PILOT_CORPUS.json v2."""

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

    def test_corpus_version_2(self):
        corpus = json.loads(
            (CONTRACTS / "FROZEN_PILOT_CORPUS.json").read_text()
        )
        parts = corpus["version"].split(".")
        assert int(parts[0]) >= 2, "Corpus must be version 2.0.0+"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Benchmark summary consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestBenchmarkSummaryConsistency:
    """Validate pilot_benchmark_summary.json v2."""

    @pytest.fixture
    def summary(self):
        path = RESULTS / "pilot_benchmark_summary.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_upgrade_completed_section(self, summary):
        assert "upgrade_completed" in summary
        assert summary["upgrade_completed"]["total"] == 3

    def test_upgrade_pilots_listed(self, summary):
        ids = {p["pilot_id"] for p in summary["upgrade_completed"]["pilots"]}
        assert ids == set(UPGRADED_PILOTS)

    def test_verdicts_correct(self, summary):
        assert summary["verdicts"]["ACCEPT"] == 5
        assert summary["verdicts"]["REJECT"] == 2
        assert summary["verdicts"]["INDETERMINATE"] == 0

    def test_all_level_b(self, summary):
        assert summary["proof_levels"]["B"]["count"] == 7
        assert summary["proof_levels"]["C"]["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 6. Cross-references valid
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
