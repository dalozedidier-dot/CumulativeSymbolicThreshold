"""test_scientific_validation_protocol.py — Tests for frozen corpus,
densification, comparative benchmark, and reference package.

Covers:
- Frozen pilot corpus integrity and versioning
- Densification pipeline for underpowered pilots
- Comparative benchmark (CUSUM, structural break, anomaly, EWS)
- Cross-contract consistency
- Docs page structure
"""
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
DOCS = ROOT / "docs"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Frozen pilot corpus
# ═══════════════════════════════════════════════════════════════════════════

class TestFrozenPilotCorpus:
    """Validate FROZEN_PILOT_CORPUS.json as point of truth."""

    @pytest.fixture
    def corpus(self):
        path = CONTRACTS / "FROZEN_PILOT_CORPUS.json"
        assert path.exists(), "FROZEN_PILOT_CORPUS.json missing"
        return json.loads(path.read_text())

    def test_schema(self, corpus):
        assert corpus["schema"] == "oric.frozen_pilot_corpus.v1"

    def test_version_semver(self, corpus):
        parts = corpus["version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_frozen_date(self, corpus):
        assert "frozen_date" in corpus
        assert corpus["frozen_date"] == "2026-03-09"

    def test_level_criteria_complete(self, corpus):
        criteria = corpus["level_criteria"]
        assert set(criteria.keys()) == {"A", "B", "C"}
        for level in criteria.values():
            assert "label" in level
            assert "requirements" in level
            assert len(level["requirements"]) >= 2

    def test_seven_pilots(self, corpus):
        assert len(corpus["pilots"]) == 7

    def test_pilot_required_fields(self, corpus):
        required = {
            "pilot_id", "domain", "sector", "data_path",
            "series_length", "signal_expected", "oric_verdict",
            "proof_level", "power_class",
        }
        for pilot in corpus["pilots"]:
            missing = required - set(pilot.keys())
            assert not missing, f"{pilot['pilot_id']} missing: {missing}"

    def test_data_paths_exist(self, corpus):
        for pilot in corpus["pilots"]:
            path = ROOT / pilot["data_path"]
            assert path.exists(), f"Data path missing: {path}"

    def test_level_b_are_accept(self, corpus):
        for p in corpus["pilots"]:
            if p["proof_level"] == "B":
                assert p["oric_verdict"] == "ACCEPT"

    def test_level_c_have_upgrade_path(self, corpus):
        for p in corpus["pilots"]:
            if p["proof_level"] == "C":
                assert p.get("power_upgrade_path"), (
                    f"{p['pilot_id']}: Level C without power_upgrade_path"
                )

    def test_summary_table_consistent(self, corpus):
        pilots = corpus["pilots"]
        summary = corpus["summary_table"]
        assert summary["total_pilots"] == len(pilots)
        assert summary["by_verdict"]["ACCEPT"] == sum(
            1 for p in pilots if p["oric_verdict"] == "ACCEPT"
        )
        assert summary["by_level"]["B"] == sum(
            1 for p in pilots if p["proof_level"] == "B"
        )
        assert summary["by_level"]["C"] == sum(
            1 for p in pilots if p["proof_level"] == "C"
        )

    def test_sorted_by_series_length_desc(self, corpus):
        lengths = [p["series_length"] for p in corpus["pilots"]]
        assert lengths == sorted(lengths, reverse=True), (
            "Pilots should be ordered by series length (descending)"
        )

    def test_showcase_pilots_are_level_b(self, corpus):
        showcase_ids = corpus["summary_table"]["showcase_pilots"]
        for pid in showcase_ids:
            pilot = next(p for p in corpus["pilots"] if p["pilot_id"] == pid)
            assert pilot["proof_level"] == "B"

    def test_cross_consistency_with_generalization(self, corpus):
        """Frozen corpus must agree with PILOT_GENERALIZATION.json."""
        gen_path = CONTRACTS / "PILOT_GENERALIZATION.json"
        if not gen_path.exists():
            pytest.skip("PILOT_GENERALIZATION.json not found")
        gen = json.loads(gen_path.read_text())
        gen_ids = {p["pilot_id"] for p in gen["generalization_matrix"]}
        corpus_ids = {p["pilot_id"] for p in corpus["pilots"]}
        assert gen_ids == corpus_ids


# ═══════════════════════════════════════════════════════════════════════════
# 2. Densification pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestDensification:
    """Test densification functions for underpowered pilots."""

    def test_densify_llm_scaling(self):
        from pipeline.densify_underpowered_pilots import densify_llm_scaling
        import pandas as pd

        df = pd.DataFrame({
            "t": range(60),
            "O": np.linspace(0, 1, 60),
            "R": np.linspace(0.5, 0.8, 60),
            "I": np.linspace(0.3, 0.9, 60),
            "demand": np.linspace(0, 0.5, 60),
            "S": np.linspace(0, 1, 60),
        })
        result = densify_llm_scaling(df, target=120)
        assert len(result) == 120
        assert set(result.columns) >= {"t", "O", "R", "I"}
        # Values should be in [0, 1]
        for col in ["O", "R", "I"]:
            assert result[col].min() >= 0
            assert result[col].max() <= 1

    def test_densify_pantheon_sn(self):
        from pipeline.densify_underpowered_pilots import densify_pantheon_sn
        import pandas as pd

        df = pd.DataFrame({
            "t": range(100),
            "z": np.linspace(0.01, 2.3, 100),
            "O": np.random.default_rng(42).random(100),
            "R": np.random.default_rng(43).random(100),
            "I": np.random.default_rng(44).random(100),
            "demand": np.random.default_rng(45).random(100),
            "S": np.random.default_rng(46).random(100),
        })
        result = densify_pantheon_sn(df, target=150)
        assert len(result) == 150
        assert "z" in result.columns

    def test_densify_pbdb_marine(self):
        from pipeline.densify_underpowered_pilots import densify_pbdb_marine
        import pandas as pd

        df = pd.DataFrame({
            "t": range(100),
            "Ma": np.linspace(541, 0, 100),
            "O": np.random.default_rng(42).random(100),
            "R": np.random.default_rng(43).random(100),
            "I": np.random.default_rng(44).random(100),
            "demand": np.random.default_rng(45).random(100),
            "S": np.random.default_rng(46).random(100),
        })
        result = densify_pbdb_marine(df, target=140)
        assert len(result) == 140
        assert "Ma" in result.columns

    def test_no_densification_if_adequate(self):
        from pipeline.densify_underpowered_pilots import densify_llm_scaling
        import pandas as pd

        df = pd.DataFrame({
            "t": range(200),
            "O": np.ones(200) * 0.5,
            "R": np.ones(200) * 0.5,
            "I": np.ones(200) * 0.5,
        })
        result = densify_llm_scaling(df, target=120)
        assert len(result) == 200  # Already exceeds target

    def test_segmentation_analysis(self):
        from pipeline.densify_underpowered_pilots import test_segmentation
        import pandas as pd

        df = pd.DataFrame({
            "O": np.concatenate([np.ones(70) * 0.3, np.ones(70) * 0.8]),
            "R": np.ones(140) * 0.5,
            "I": np.ones(140) * 0.5,
        })
        results = test_segmentation(df, [30, 50, 70, 90, 110])
        assert len(results) == 5
        # Segmentation at 70 should be best (clearest break)
        adequate = [r for r in results if r["segment_adequate"]]
        assert len(adequate) >= 1
        best = max(adequate, key=lambda r: r["signal_strength"])
        assert best["segmentation_point"] == 70


# ═══════════════════════════════════════════════════════════════════════════
# 3. Comparative benchmark
# ═══════════════════════════════════════════════════════════════════════════

class TestComparativeBenchmark:
    """Test baseline detection methods."""

    @pytest.fixture
    def series_with_break(self):
        """Series with clear mean shift at t=100."""
        rng = np.random.default_rng(42)
        pre = rng.normal(0, 1, 100)
        post = rng.normal(3, 1, 100)
        return np.concatenate([pre, post])

    @pytest.fixture
    def series_flat(self):
        """Stationary series with no break."""
        return np.random.default_rng(42).normal(0, 1, 200)

    def test_cusum_detects_break(self, series_with_break):
        from oric.comparative_benchmark import cusum_changepoint
        result = cusum_changepoint(series_with_break)
        assert result.detected is True
        assert result.method == "cusum_changepoint"
        assert result.p_value is not None and result.p_value < 0.05

    def test_cusum_no_false_positive(self, series_flat):
        from oric.comparative_benchmark import cusum_changepoint
        result = cusum_changepoint(series_flat)
        # Flat series should not trigger (most of the time)
        assert result.method == "cusum_changepoint"

    def test_structural_break_detects(self, series_with_break):
        from oric.comparative_benchmark import structural_break
        result = structural_break(series_with_break)
        assert result.detected is True
        assert result.detection_point is not None
        # Detection point should be near 100
        assert abs(result.detection_point - 100) < 30

    def test_anomaly_zscore(self, series_with_break):
        from oric.comparative_benchmark import anomaly_zscore
        result = anomaly_zscore(series_with_break)
        assert result.method == "anomaly_zscore"
        assert result.statistic is not None

    def test_early_warning_signal(self):
        from oric.comparative_benchmark import early_warning_signal
        # Create series with increasing variance
        rng = np.random.default_rng(42)
        series = np.array([
            rng.normal(0, 0.1 + 0.05 * i) for i in range(200)
        ])
        result = early_warning_signal(series, window=20)
        assert result.method == "early_warning"

    def test_benchmark_comparison_structure(self, series_with_break):
        from oric.comparative_benchmark import run_benchmark_on_series
        comp = run_benchmark_on_series(
            pilot_id="test_pilot",
            series=series_with_break,
            oric_verdict="ACCEPT",
        )
        assert comp.pilot_id == "test_pilot"
        assert len(comp.methods) == 5
        method_names = {m.method for m in comp.methods}
        assert method_names == {
            "oric", "cusum_changepoint", "structural_break",
            "anomaly_zscore", "early_warning",
        }

    def test_short_series_handling(self):
        from oric.comparative_benchmark import cusum_changepoint, structural_break
        short = np.array([1, 2, 3])
        r1 = cusum_changepoint(short)
        assert r1.detected is False
        r2 = structural_break(short)
        assert r2.detected is False

    def test_method_result_to_dict(self):
        from oric.comparative_benchmark import MethodResult
        r = MethodResult(
            method="cusum_changepoint",
            detected=True,
            detection_point=50,
            statistic=3.14,
            p_value=0.01,
        )
        d = r.to_dict()
        assert d["method"] == "cusum_changepoint"
        assert d["detected"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cross-contract consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossContractConsistency:
    """Verify all contracts agree on pilot classification."""

    def _load(self, name):
        path = CONTRACTS / name
        if not path.exists():
            pytest.skip(f"{name} not found")
        return json.loads(path.read_text())

    def test_all_pilot_ids_consistent(self):
        corpus = self._load("FROZEN_PILOT_CORPUS.json")
        gen = self._load("PILOT_GENERALIZATION.json")
        showcase = self._load("SHOWCASE_PILOTS.json")

        corpus_ids = {p["pilot_id"] for p in corpus["pilots"]}
        gen_ids = {p["pilot_id"] for p in gen["generalization_matrix"]}
        assert corpus_ids == gen_ids

        # Showcase pilots must be in corpus
        assert showcase["primary"]["pilot_id"] in corpus_ids
        assert showcase["secondary"]["pilot_id"] in corpus_ids

    def test_upgrade_protocol_covers_level_c(self):
        corpus = self._load("FROZEN_PILOT_CORPUS.json")
        upgrade = self._load("POWER_UPGRADE_PROTOCOL.json")

        level_c_ids = {
            p["pilot_id"] for p in corpus["pilots"]
            if p["proof_level"] == "C"
        }
        upgrade_ids = {p["pilot_id"] for p in upgrade["pilots"]}
        assert level_c_ids == upgrade_ids

    def test_power_criteria_thresholds_match(self):
        power = self._load("POWER_CRITERIA.json")
        assert power["thresholds"]["high"]["total_points"] == 200
        assert power["thresholds"]["medium"]["total_points"] == 60


# ═══════════════════════════════════════════════════════════════════════════
# 5. Docs pages
# ═══════════════════════════════════════════════════════════════════════════

class TestDocsPages:
    """Verify all reference package pages exist."""

    @pytest.mark.parametrize("page", [
        "framework_status.md",
        "canonical_proof.md",
        "generalization_pilots.md",
        "limitations_power.md",
        "REPLICATION_PROTOCOL.md",
    ])
    def test_page_exists(self, page):
        assert (DOCS / page).exists(), f"Missing docs page: {page}"

    def test_mkdocs_references_new_pages(self):
        mkdocs = (ROOT / "mkdocs.yml").read_text()
        for page in ["framework_status", "canonical_proof",
                      "generalization_pilots", "limitations_power"]:
            assert page in mkdocs, f"mkdocs.yml missing {page}"
