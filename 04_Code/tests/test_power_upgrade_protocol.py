"""test_power_upgrade_protocol.py — Contractual tests for the power upgrade pipeline.

Ensures that:
- The upgrade does not change the research question
- Proxy definitions remain consistent
- n_after > n_before
- Power class improves or is justified
- Homogeneity checks pass
- Upgrade reports are structurally valid
- The protocol contract is internally consistent
"""
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
DATA = ROOT / "03_Data"
RESULTS = ROOT / "05_Results"
PILOTS_UPGRADE = RESULTS / "pilots" / "power_upgrade"

LEVEL_C_PILOTS = [
    "sector_cosmo.pilot_pantheon_sn",
    "sector_bio.pilot_pbdb_marine",
    "sector_ai_tech.pilot_llm_scaling",
]

PILOT_DATA_DIRS = {
    "sector_cosmo.pilot_pantheon_sn": DATA / "sector_cosmo" / "real" / "pilot_pantheon_sn",
    "sector_bio.pilot_pbdb_marine": DATA / "sector_bio" / "real" / "pilot_pbdb_marine",
    "sector_ai_tech.pilot_llm_scaling": DATA / "sector_ai_tech" / "real" / "pilot_llm_scaling",
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Protocol contract integrity
# ═══════════════════════════════════════════════════════════════════════════

class TestProtocolContract:
    """Validate contracts/POWER_UPGRADE_PROTOCOL.json structure."""

    @pytest.fixture
    def protocol(self):
        path = CONTRACTS / "POWER_UPGRADE_PROTOCOL.json"
        assert path.exists(), "POWER_UPGRADE_PROTOCOL.json missing"
        return json.loads(path.read_text())

    def test_schema(self, protocol):
        assert protocol["schema"] == "oric.power_upgrade_protocol.v1"

    def test_version_2(self, protocol):
        assert protocol["version"] == "2.0"

    def test_core_principle_present(self, protocol):
        assert "core_principle" in protocol
        assert "decidabilite" in protocol["core_principle"].lower()

    def test_invariants_declared(self, protocol):
        inv = protocol["invariants"]
        assert "research_question_unchanged" in inv
        assert "primary_proxy_unchanged" in inv
        assert "time_axis_homogeneous" in inv
        assert "no_post_hoc_selection" in inv

    def test_three_pilots(self, protocol):
        assert len(protocol["pilots"]) == 3

    def test_anti_gaming_clause(self, protocol):
        assert "anti_gaming_clause" in protocol

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_pilot_has_upgrade_plan(self, protocol, pilot_id):
        pilot = next(
            (p for p in protocol["pilots"] if p["pilot_id"] == pilot_id), None
        )
        assert pilot is not None, f"Missing pilot {pilot_id} in protocol"
        plan = pilot["upgrade_plan"]
        assert "dataset_source_upgrade" in plan
        assert "primary_variable_unchanged" in plan
        assert "primary_proxy_unchanged" in plan
        assert "segment_structurally_missing" in plan
        assert "bias_risks" in plan
        assert "stability_tests_required" in plan
        assert "what_is_allowed_to_change" in plan
        assert "what_cannot_change" in plan

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_pilot_has_success_criteria(self, protocol, pilot_id):
        pilot = next(p for p in protocol["pilots"] if p["pilot_id"] == pilot_id)
        sc = pilot["success_criteria"]
        assert sc["min_total_points"] >= 120
        assert sc["min_points_per_segment"] >= 60
        assert sc["precheck_must_pass"] is True
        assert sc["verdict_must_be_decidable"] is True
        assert sc["homogeneity_check_must_pass"] is True

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_pilot_has_segmentation_candidates(self, protocol, pilot_id):
        pilot = next(p for p in protocol["pilots"] if p["pilot_id"] == pilot_id)
        candidates = pilot["upgrade_plan"]["segmentation_candidates"]
        assert len(candidates) >= 3
        for c in candidates:
            assert "rationale" in c


# ═══════════════════════════════════════════════════════════════════════════
# 2. Data directory structure
# ═══════════════════════════════════════════════════════════════════════════

class TestPilotDataDirectories:
    """Validate pilot data directory structure for each Level C pilot."""

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_real_csv_exists(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        assert (d / "real.csv").exists()

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_real_densified_csv_exists(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        assert (d / "real_densified.csv").exists()

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_upgrade_plan_exists(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        assert (d / "upgrade_plan.json").exists()

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_readme_exists(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        assert (d / "README.md").exists()

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_raw_dir_exists(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        assert (d / "raw").is_dir()

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_processed_dir_exists(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        assert (d / "processed").is_dir()

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_proxy_spec_unchanged(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        spec = json.loads((d / "proxy_spec.json").read_text())
        # All specs must have O, R, I, demand, S columns
        col_names = {c["oric_variable"] for c in spec["columns"]}
        assert {"O", "R", "I", "demand", "S"} == col_names


# ═══════════════════════════════════════════════════════════════════════════
# 3. Upgrade does not change research question
# ═══════════════════════════════════════════════════════════════════════════

class TestUpgradeInvariants:
    """Ensure densified data preserves proxy structure."""

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_densified_has_more_rows(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        df_before = pd.read_csv(d / "real.csv")
        df_after = pd.read_csv(d / "real_densified.csv")
        assert len(df_after) > len(df_before)

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_oric_columns_preserved(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        df_after = pd.read_csv(d / "real_densified.csv")
        for col in ["O", "R", "I", "demand", "S"]:
            assert col in df_after.columns, f"Missing ORIC column {col}"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_proxy_values_in_range(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        df = pd.read_csv(d / "real_densified.csv")
        for col in ["O", "R", "I", "demand", "S"]:
            if col in df.columns:
                assert df[col].min() >= -0.01, f"{col} has values below 0"
                assert df[col].max() <= 1.01, f"{col} has values above 1"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_homogeneity_mean_shift_acceptable(self, pilot_id):
        """Mean shift < 0.3 for each proxy between original and densified."""
        d = PILOT_DATA_DIRS[pilot_id]
        df_before = pd.read_csv(d / "real.csv")
        df_after = pd.read_csv(d / "real_densified.csv")
        for col in ["O", "R", "I", "demand", "S"]:
            if col in df_before.columns and col in df_after.columns:
                shift = abs(df_after[col].mean() - df_before[col].mean())
                assert shift < 0.3, (
                    f"Mean shift for {col} is {shift:.4f} (threshold: 0.3)"
                )

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_homogeneity_std_ratio_acceptable(self, pilot_id):
        """Std ratio between 0.5 and 2.0 for each proxy."""
        d = PILOT_DATA_DIRS[pilot_id]
        df_before = pd.read_csv(d / "real.csv")
        df_after = pd.read_csv(d / "real_densified.csv")
        for col in ["O", "R", "I", "demand", "S"]:
            if col in df_before.columns and col in df_after.columns:
                std_b = df_before[col].std()
                std_a = df_after[col].std()
                if std_b > 1e-10:
                    ratio = std_a / std_b
                    assert 0.5 < ratio < 2.0, (
                        f"Std ratio for {col} is {ratio:.4f} (must be 0.5-2.0)"
                    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Upgrade plan consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestUpgradePlanConsistency:
    """Validate local upgrade_plan.json files."""

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_upgrade_plan_matches_data(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        plan = json.loads((d / "upgrade_plan.json").read_text())
        df_before = pd.read_csv(d / "real.csv")
        df_after = pd.read_csv(d / "real_densified.csv")
        assert plan["current_dataset"]["n_rows"] == len(df_before)
        assert plan["densified_dataset"]["n_rows"] == len(df_after)

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_upgrade_plan_has_invariants(self, pilot_id):
        d = PILOT_DATA_DIRS[pilot_id]
        plan = json.loads((d / "upgrade_plan.json").read_text())
        inv = plan["invariants"]
        assert "proxy_O" in inv
        assert "proxy_R" in inv
        assert "proxy_I" in inv
        assert "proxy_demand" in inv
        assert "proxy_S" in inv
        assert inv["normalization"] == "robust_minmax"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Upgrade report outputs
# ═══════════════════════════════════════════════════════════════════════════

class TestUpgradeReportOutputs:
    """Validate upgrade reports in 05_Results/pilots/power_upgrade/."""

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_report_json_exists(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "power_upgrade_report.json"
        assert path.exists(), f"Missing report: {path}"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_precheck_comparison_exists(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "precheck_comparison.json"
        assert path.exists(), f"Missing precheck comparison: {path}"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_markdown_report_exists(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "power_upgrade_report.md"
        assert path.exists(), f"Missing markdown report: {path}"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_report_schema(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "power_upgrade_report.json"
        report = json.loads(path.read_text())
        assert report["schema"] == "oric.power_upgrade_report.v1"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_report_has_required_fields(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "power_upgrade_report.json"
        report = json.loads(path.read_text())
        for field in [
            "n_before", "n_after",
            "power_class_before", "power_class_after",
            "segment_counts_before", "segment_counts_after",
            "precheck_before", "precheck_after",
            "homogeneity_checks", "homogeneity_passed",
            "upgrade_status", "level_before", "level_after",
            "justification",
        ]:
            assert field in report, f"Missing field: {field}"

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_report_n_after_gt_n_before(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "power_upgrade_report.json"
        report = json.loads(path.read_text())
        assert report["n_after"] > report["n_before"]

    @pytest.mark.parametrize("pilot_id", LEVEL_C_PILOTS)
    def test_report_homogeneity_passed(self, pilot_id):
        path = PILOTS_UPGRADE / pilot_id.replace(".", "/") / "power_upgrade_report.json"
        report = json.loads(path.read_text())
        assert report["homogeneity_passed"] is True

    def test_summary_v2_exists(self):
        path = PILOTS_UPGRADE / "power_upgrade_summary_v2.json"
        assert path.exists()
        summary = json.loads(path.read_text())
        assert summary["schema"] == "oric.power_upgrade_summary.v2"
        assert summary["total_pilots"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# 6. PBDB marine binning variants
# ═══════════════════════════════════════════════════════════════════════════

class TestPBDBBinningVariants:
    """Validate PBDB marine intermediate binning variants."""

    def test_stage_binning_exists(self):
        path = DATA / "sector_bio" / "real" / "pilot_pbdb_marine" / "processed" / "real_binning_stage.csv"
        assert path.exists()

    def test_10myr_binning_exists(self):
        path = DATA / "sector_bio" / "real" / "pilot_pbdb_marine" / "processed" / "real_binning_10myr.csv"
        assert path.exists()

    def test_5myr_binning_exists(self):
        path = DATA / "sector_bio" / "real" / "pilot_pbdb_marine" / "processed" / "real_binning_5myr.csv"
        assert path.exists()

    def test_binning_order_by_size(self):
        base = DATA / "sector_bio" / "real" / "pilot_pbdb_marine" / "processed"
        n_stage = len(pd.read_csv(base / "real_binning_stage.csv"))
        n_10 = len(pd.read_csv(base / "real_binning_10myr.csv"))
        n_5 = len(pd.read_csv(base / "real_binning_5myr.csv"))
        assert n_stage <= n_10 <= n_5


# ═══════════════════════════════════════════════════════════════════════════
# 7. tools/power_upgrade.py importability
# ═══════════════════════════════════════════════════════════════════════════

class TestPowerUpgradeTool:
    """Validate tools/power_upgrade.py exists and is valid Python."""

    def test_script_exists(self):
        assert (ROOT / "tools" / "power_upgrade.py").exists()

    def test_script_compiles(self):
        import py_compile
        py_compile.compile(
            str(ROOT / "tools" / "power_upgrade.py"),
            doraise=True,
        )
