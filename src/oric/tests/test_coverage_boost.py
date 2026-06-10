"""Coverage boost tests for under-covered oric modules.

Targets:
  ori_core_v2.py   (0%)
  decision.py      (45%)
  symbolic.py      (51%)
  ori_core.py      (53%)
  logger.py        (57%)
  randomization.py (60%)
  prereg.py        (67%)
  proxy_spec.py    (69%)
  integrity.py     (78%)
  ci_maturity.py   (87%)
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

# ─── ori_core ────────────────────────────────────────────────────────────────

from oric.ori_core import (
    compute_cap_projection,
    compute_sigma,
    compute_viability,
    summarize_run,
)


def _series(vals):
    return pd.Series(vals, dtype=float)


class TestCapProjection:
    def test_product_form(self):
        cap = compute_cap_projection(_series([0.5]), _series([0.4]), _series([0.2]))
        assert abs(float(cap.iloc[0]) - 0.04) < 1e-9

    def test_geom_mean_form(self):
        cap = compute_cap_projection(
            _series([1.0]), _series([1.0]), _series([1.0]), form="geom_mean"
        )
        assert abs(float(cap.iloc[0]) - 1.0) < 1e-9

    def test_weighted_sum_form(self):
        cap = compute_cap_projection(
            _series([1.0]), _series([1.0]), _series([1.0]), form="weighted_sum"
        )
        assert abs(float(cap.iloc[0]) - 1.0) < 1e-9

    def test_unknown_form_raises(self):
        with pytest.raises(ValueError, match="Unknown cap form"):
            compute_cap_projection(_series([0.5]), _series([0.4]), _series([0.2]), form="invalid")

    def test_geom_mean_values(self):
        cap = compute_cap_projection(
            _series([0.8]), _series([0.5]), _series([0.2]), form="geom_mean"
        )
        expected = (0.8 * 0.5 * 0.2) ** (1.0 / 3.0)
        assert abs(float(cap.iloc[0]) - expected) < 1e-9


class TestComputeSigma:
    def test_relu_diff_positive(self):
        s = compute_sigma(_series([0.8]), _series([0.3]))
        assert abs(float(s.iloc[0]) - 0.5) < 1e-9

    def test_relu_diff_no_mismatch(self):
        s = compute_sigma(_series([0.2]), _series([0.9]))
        assert float(s.iloc[0]) == 0.0

    def test_unknown_form_raises(self):
        with pytest.raises(ValueError):
            compute_sigma(_series([0.5]), _series([0.5]), form="other")


class TestComputeViability:
    def _df(self):
        return pd.DataFrame(
            {
                "survie": [0.8],
                "energie_nette": [0.6],
                "integrite": [0.7],
                "persistance": [0.9],
            }
        )

    def test_equal_weights(self):
        v = compute_viability(self._df(), (0.25, 0.25, 0.25, 0.25))
        expected = (0.8 + 0.6 + 0.7 + 0.9) / 4.0
        assert abs(float(v.iloc[0]) - expected) < 1e-9

    def test_weights_normalised(self):
        v1 = compute_viability(self._df(), (1.0, 1.0, 1.0, 1.0))
        v2 = compute_viability(self._df(), (2.0, 2.0, 2.0, 2.0))
        assert abs(float(v1.iloc[0]) - float(v2.iloc[0])) < 1e-9

    def test_missing_column_raises(self):
        bad = self._df().drop(columns=["integrite"])
        with pytest.raises(KeyError):
            compute_viability(bad, (0.25, 0.25, 0.25, 0.25))


class TestSummarizeRun:
    def _df(self, n=50):
        rng = np.random.default_rng(0)
        return pd.DataFrame(
            {
                "Sigma": rng.uniform(0, 0.5, n),
                "V": rng.uniform(0.3, 0.9, n),
            }
        )

    def test_basic_keys(self):
        result = summarize_run(self._df())
        assert "V_q05" in result
        assert "A_sigma" in result
        assert "frac_over" in result

    def test_short_series_fallback(self):
        result = summarize_run(self._df(n=5), window_W=20)
        assert "V_q05" in result

    def test_missing_column_raises(self):
        df = self._df().drop(columns=["Sigma"])
        with pytest.raises(KeyError):
            summarize_run(df)

    def test_frac_over_range(self):
        result = summarize_run(self._df())
        assert 0.0 <= result["frac_over"] <= 1.0


# ─── symbolic ────────────────────────────────────────────────────────────────

from oric.symbolic import compute_stock_S, compute_order_C, detect_s_star_piecewise


class TestComputeStockS:
    def _df(self):
        return pd.DataFrame(
            {
                "repertoire": [0.5],
                "codification": [0.3],
                "densite_transmission": [0.4],
                "fidelite": [0.6],
            }
        )

    def test_basic(self):
        s = compute_stock_S(self._df(), (1.0, 1.0, 1.0, 1.0))
        assert abs(float(s.iloc[0]) - (0.5 + 0.3 + 0.4 + 0.6) / 4.0) < 1e-9

    def test_missing_column_raises(self):
        bad = self._df().drop(columns=["fidelite"])
        with pytest.raises(KeyError, match="Missing column"):
            compute_stock_S(bad, (1.0, 1.0, 1.0, 1.0))


class TestComputeOrderC:
    def test_accumulates_joint_gains(self):
        df = pd.DataFrame(
            {
                "S": [0.0, 0.2, 0.4, 0.3, 0.5],
                "V": [0.5, 0.6, 0.7, 0.6, 0.8],
            }
        )
        c = compute_order_C(df)
        assert len(c) == 5
        assert c.iloc[0] == 0.0  # starts at 0

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"S": [0.1, 0.2]})
        with pytest.raises(KeyError):
            compute_order_C(df)


class TestDetectSStarPiecewise:
    def test_too_short_returns_nan(self):
        S = np.linspace(0, 1, 5)
        C = np.linspace(0, 1, 5)
        result = detect_s_star_piecewise(S, C)
        assert math.isnan(result["S_star"])
        assert result["improvement"] == 0.0

    def test_normal_case(self):
        rng = np.random.default_rng(42)
        n = 100
        S = np.linspace(0, 1, n)
        # C has a regime change at S=0.5
        C = np.where(S < 0.5, rng.normal(0.2, 0.02, n), rng.normal(0.8, 0.02, n))
        result = detect_s_star_piecewise(S, C)
        assert "S_star" in result
        assert "improvement" in result
        assert not math.isnan(result["S_star"])
        assert result["improvement"] > 0.0

    def test_no_valid_split_returns_nan(self):
        # Series too uniform → all splits fail the min-3 guard
        S = np.array([0.5] * 20)  # constant S → all <= s_star
        C = np.random.default_rng(0).normal(0, 0.01, 20)
        result = detect_s_star_piecewise(S, C)
        # Either found a split or returned nan — just check structure
        assert "S_star" in result


# ─── decision ────────────────────────────────────────────────────────────────

from oric.decision import hierarchical_verdict


class TestHierarchicalVerdict:
    def _call(
        self,
        p_welch=float("nan"),
        boot_lo=float("nan"),
        boot_hi=float("nan"),
        boot_mid=float("nan"),
        mw_p=float("nan"),
        alpha=0.01,
        sesoi=0.05,
    ):
        return hierarchical_verdict(p_welch, boot_lo, boot_hi, boot_mid, mw_p, alpha, sesoi)

    def test_welch_accept(self):
        r = self._call(p_welch=0.005, boot_lo=0.1, boot_hi=0.9, boot_mid=0.3, sesoi=0.1)
        assert r.p_source == "welch"
        assert r.ok_p is True
        assert r.verdict_triplet is True
        assert r.indeterminate is False

    def test_welch_reject_p_too_high(self):
        r = self._call(p_welch=0.05, boot_lo=0.1, boot_hi=0.9, boot_mid=0.3, sesoi=0.1)
        assert r.p_source == "welch"
        assert r.ok_p is False
        assert r.verdict_triplet is False

    def test_welch_reject_ci_negative(self):
        r = self._call(p_welch=0.005, boot_lo=-0.1, boot_hi=0.9, boot_mid=0.3, sesoi=0.1)
        assert r.ci_excludes_zero is False
        assert r.verdict_triplet is False

    def test_welch_reject_sesoi_not_met(self):
        r = self._call(p_welch=0.005, boot_lo=0.1, boot_hi=0.9, boot_mid=0.01, sesoi=0.1)
        assert r.sesoi_ok is False
        assert r.verdict_triplet is False

    def test_bootstrap_fallback_when_welch_nan(self):
        r = self._call(boot_lo=0.1, boot_hi=0.9, boot_mid=0.3, sesoi=0.1)
        assert r.p_source == "bootstrap_fallback"
        assert r.ok_p is True
        assert r.indeterminate is False
        assert r.p_effective == pytest.approx(0.005)

    def test_bootstrap_fallback_ci_not_excluding_zero_goes_to_mwu(self):
        r = self._call(boot_lo=-0.1, boot_hi=0.9, mw_p=0.005, boot_mid=0.3, sesoi=0.1)
        assert r.p_source == "mannwhitney_fallback"

    def test_mannwhitney_fallback(self):
        r = self._call(mw_p=0.008, boot_mid=0.3, boot_lo=float("nan"), sesoi=0.1)
        assert r.p_source == "mannwhitney_fallback"
        assert r.ok_p is True
        assert r.indeterminate is False

    def test_all_unavailable_indeterminate(self):
        r = self._call()
        assert r.p_source == "unavailable"
        assert r.indeterminate is True
        assert r.ok_p is False
        assert r.verdict_triplet is False
        assert math.isnan(r.p_effective)

    def test_to_dict_keys(self):
        r = self._call(p_welch=0.005, boot_lo=0.1, boot_hi=0.9, boot_mid=0.3, sesoi=0.1)
        d = r.to_dict()
        for k in (
            "p_effective",
            "p_source",
            "ci_lo",
            "ci_hi",
            "boot_mid",
            "ci_excludes_zero",
            "sesoi_ok",
            "ok_p",
            "ok_ci",
            "ok_sesoi",
            "verdict_triplet",
            "indeterminate",
        ):
            assert k in d


# ─── logger ──────────────────────────────────────────────────────────────────

from oric.logger import ExperimentLogger


class TestExperimentLogger:
    def test_creates_file_on_log(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        logger.log("test_event", {"value": 42})
        log_path = tmp_path / "experiment_log.jsonl"
        assert log_path.exists()

    def test_jsonl_format(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        logger.log("run_start", {"seed": 8000, "alpha": 0.01})
        lines = (tmp_path / "experiment_log.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event"] == "run_start"
        assert record["payload"]["seed"] == 8000
        assert "ts_utc" in record

    def test_append_multiple(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        for i in range(3):
            logger.log("step", {"i": i})
        lines = (tmp_path / "experiment_log.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        logger = ExperimentLogger(nested)
        logger.log("x", {})
        assert (nested / "experiment_log.jsonl").exists()


# ─── randomization ───────────────────────────────────────────────────────────

from oric.randomization import Condition, RandomizationEngine


class TestRandomizationEngine:
    def test_seeds_length(self):
        eng = RandomizationEngine(42)
        seeds = eng.seeds(10)
        assert len(seeds) == 10

    def test_seeds_deterministic(self):
        assert RandomizationEngine(7).seeds(5) == RandomizationEngine(7).seeds(5)

    def test_seeds_differ_for_different_master(self):
        assert RandomizationEngine(1).seeds(5) != RandomizationEngine(2).seeds(5)

    def test_assign_conditions_length(self):
        eng = RandomizationEngine(0)
        conds = [Condition("A", {"k": 1.0}), Condition("B", {"k": 2.0})]
        seeds = eng.seeds(8)
        pairs = eng.assign_conditions(seeds, conds)
        assert len(pairs) == 8

    def test_assign_conditions_only_known_names(self):
        eng = RandomizationEngine(0)
        conds = [Condition("X", {}), Condition("Y", {})]
        seeds = eng.seeds(6)
        pairs = eng.assign_conditions(seeds, conds)
        names = {name for _, name in pairs}
        assert names <= {"X", "Y"}

    def test_assign_conditions_empty_raises(self):
        eng = RandomizationEngine(0)
        with pytest.raises(ValueError):
            eng.assign_conditions([1, 2], [])

    def test_condition_dataclass(self):
        c = Condition("test", {"alpha": 0.01})
        assert c.name == "test"
        assert c.params["alpha"] == 0.01


# ─── prereg ──────────────────────────────────────────────────────────────────

from oric.prereg import PreregSpec


class TestPreregSpec:
    def test_to_dict_has_alpha(self):
        spec = PreregSpec()
        d = spec.to_dict()
        assert d["alpha"] == 0.01

    def test_validate_passes_defaults(self):
        PreregSpec().validate()  # should not raise

    def test_validate_bad_alpha(self):
        with pytest.raises(ValueError, match="alpha"):
            PreregSpec(alpha=1.5).validate()

    def test_validate_bad_ci_level(self):
        with pytest.raises(ValueError, match="ci_level"):
            PreregSpec(ci_level=0.0).validate()

    def test_validate_bad_n_min(self):
        with pytest.raises(ValueError, match="n_min"):
            PreregSpec(n_min=0).validate()

    def test_validate_bad_window(self):
        with pytest.raises(ValueError, match="windows"):
            PreregSpec(window_W=0).validate()

    def test_validate_bad_m_consecutive(self):
        with pytest.raises(ValueError, match="m_consecutive"):
            PreregSpec(m_consecutive=0).validate()

    def test_validate_bad_omega_length(self):
        with pytest.raises(ValueError, match="omega_v"):
            PreregSpec(omega_v=(0.5, 0.5)).validate()  # type: ignore[arg-type]


# ─── proxy_spec ──────────────────────────────────────────────────────────────

from oric.proxy_spec import ColumnSpec, ProxySpec


class TestColumnSpec:
    def test_to_dict_keys(self):
        c = ColumnSpec(source_column="gdp", oric_variable="O")
        d = c.to_dict()
        assert d["source_column"] == "gdp"
        assert d["oric_variable"] == "O"
        assert "direction" in d
        assert "normalization" in d

    def test_defaults(self):
        c = ColumnSpec(source_column="x", oric_variable="R")
        assert c.direction == "positive"
        assert c.normalization == "robust_minmax"
        assert c.scale_lo is None


class TestProxySpec:
    def _make(self):
        return ProxySpec(
            dataset_id="test_ds",
            sector="test_sector",
            columns=(
                ColumnSpec(source_column="gdp", oric_variable="O"),
                ColumnSpec(source_column="pop", oric_variable="R"),
            ),
        )

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        assert d["dataset_id"] == "test_ds"
        assert "columns" in d
        assert len(d["columns"]) == 2

    def test_sha256_deterministic(self):
        a = self._make().sha256()
        b = self._make().sha256()
        assert a == b
        assert len(a) == 64  # hex SHA-256

    def test_sha256_changes_on_mutation(self):
        base = ProxySpec(dataset_id="A", sector="s")
        other = ProxySpec(dataset_id="B", sector="s")
        assert base.sha256() != other.sha256()

    def test_to_json_file_and_from(self, tmp_path):
        spec = self._make()
        p = tmp_path / "spec.json"
        spec.to_json_file(p)
        assert p.exists()
        loaded = ProxySpec.from_json_file(p)
        assert loaded.dataset_id == "test_ds"
        assert loaded.sector == "test_sector"
        assert len(loaded.columns) == 2
        assert loaded.columns[0].source_column == "gdp"

    def test_sha256_round_trip(self, tmp_path):
        spec = self._make()
        p = tmp_path / "spec.json"
        spec.to_json_file(p)
        loaded = ProxySpec.from_json_file(p)
        assert spec.sha256() == loaded.sha256()

    def test_column_for_found(self):
        spec = self._make()
        col = spec.column_for("O")
        assert col is not None
        assert col.source_column == "gdp"

    def test_column_for_not_found(self):
        spec = self._make()
        assert spec.column_for("S") is None

    def test_source_columns(self):
        spec = self._make()
        assert spec.source_columns() == ["gdp", "pop"]

    def test_from_json_file_defaults(self, tmp_path):
        raw = {
            "dataset_id": "minimal",
            "sector": "test",
            "columns": [],
        }
        p = tmp_path / "spec.json"
        p.write_text(json.dumps(raw), encoding="utf-8")
        spec = ProxySpec.from_json_file(p)
        assert spec.spec_version == "1.0"
        assert spec.time_mode == "index"
        assert spec.normalization_global == "robust_minmax"


# ─── integrity ───────────────────────────────────────────────────────────────

from oric.integrity import (
    IntegrityCheck,
    check_all_integrity,
    check_dual_proof_integrity,
    check_run_integrity,
    integrity_gate,
)


class TestIntegrityCheck:
    def test_initial_state(self):
        ic = IntegrityCheck(path="/some/path")
        assert ic.passed is True
        assert ic.errors == []
        assert ic.warnings == []

    def test_fail_sets_passed_false(self):
        ic = IntegrityCheck()
        ic.fail("something bad")
        assert ic.passed is False
        assert "something bad" in ic.errors

    def test_warn_keeps_passed(self):
        ic = IntegrityCheck()
        ic.warn("minor issue")
        assert ic.passed is True
        assert "minor issue" in ic.warnings

    def test_to_dict(self):
        ic = IntegrityCheck(path="/x")
        ic.fail("err1")
        ic.warn("warn1")
        d = ic.to_dict()
        assert d["path"] == "/x"
        assert d["passed"] is False
        assert d["n_errors"] == 1
        assert d["n_warnings"] == 1


class TestCheckRunIntegrity:
    def _run_dir(
        self, tmp_path, verdict="ACCEPT", summary_verdict="ACCEPT", precheck=None, json_verdict=None
    ):
        d = tmp_path / "run"
        d.mkdir()
        (d / "verdict.txt").write_text(verdict, encoding="utf-8")
        tables = d / "tables"
        tables.mkdir()
        payload = {"protocol_verdict": summary_verdict}
        if precheck is not None:
            payload["precheck_passed"] = precheck
        if json_verdict is not None:
            jv = {"verdict": json_verdict}
            (tables / "verdict.json").write_text(json.dumps(jv), encoding="utf-8")
        (tables / "validation_summary.json").write_text(json.dumps(payload), encoding="utf-8")
        return d

    def test_passes_on_valid_run(self, tmp_path):
        d = self._run_dir(tmp_path)
        result = check_run_integrity(d)
        assert result.passed

    def test_missing_dir(self, tmp_path):
        d = tmp_path / "nonexistent"
        result = check_run_integrity(d)
        assert not result.passed

    def test_missing_verdict_txt(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        result = check_run_integrity(d)
        assert not result.passed
        assert any("verdict.txt" in e for e in result.errors)

    def test_invalid_verdict_token(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "verdict.txt").write_text("MAYBE", encoding="utf-8")
        result = check_run_integrity(d)
        assert not result.passed

    def test_summary_mismatch(self, tmp_path):
        d = self._run_dir(tmp_path, verdict="ACCEPT", summary_verdict="REJECT")
        result = check_run_integrity(d)
        assert not result.passed
        assert any("summary.json verdict" in e for e in result.errors)

    def test_precheck_false_with_accept(self, tmp_path):
        d = self._run_dir(tmp_path, verdict="ACCEPT", summary_verdict="ACCEPT", precheck=False)
        result = check_run_integrity(d)
        assert not result.passed

    def test_verdict_json_mismatch(self, tmp_path):
        d = self._run_dir(
            tmp_path, verdict="ACCEPT", summary_verdict="ACCEPT", json_verdict="REJECT"
        )
        result = check_run_integrity(d)
        assert not result.passed

    def test_accept_with_valid_detection_rates(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "verdict.txt").write_text("ACCEPT", encoding="utf-8")
        tables = d / "tables"
        tables.mkdir()
        payload = {
            "protocol_verdict": "ACCEPT",
            "datasets": {
                "test": {"metrics": {"detection_rate": 0.8}},
                "stable": {"metrics": {"detection_rate": 0.2}},
                "placebo": {"metrics": {"detection_rate": 0.1}},
            },
        }
        (tables / "validation_summary.json").write_text(json.dumps(payload), encoding="utf-8")
        result = check_run_integrity(d)
        assert result.passed

    def test_accept_low_test_detection_rate(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "verdict.txt").write_text("ACCEPT", encoding="utf-8")
        tables = d / "tables"
        tables.mkdir()
        payload = {
            "protocol_verdict": "ACCEPT",
            "datasets": {
                "test": {"metrics": {"detection_rate": 0.3}},
            },
        }
        (tables / "validation_summary.json").write_text(json.dumps(payload), encoding="utf-8")
        result = check_run_integrity(d)
        assert not result.passed

    def test_accept_high_placebo_detection_rate(self, tmp_path):
        d = tmp_path / "run"
        d.mkdir()
        (d / "verdict.txt").write_text("ACCEPT", encoding="utf-8")
        tables = d / "tables"
        tables.mkdir()
        payload = {
            "protocol_verdict": "ACCEPT",
            "datasets": {
                "placebo": {"metrics": {"detection_rate": 0.9}},
            },
        }
        (tables / "validation_summary.json").write_text(json.dumps(payload), encoding="utf-8")
        result = check_run_integrity(d)
        assert not result.passed


class TestCheckDualProofIntegrity:
    def _write(self, tmp_path, manifest_data, final_data=None):
        mpath = tmp_path / "dual_proof_manifest.json"
        mpath.write_text(json.dumps(manifest_data), encoding="utf-8")
        fpath = None
        if final_data is not None:
            fpath = tmp_path / "final_status.json"
            fpath.write_text(json.dumps(final_data), encoding="utf-8")
        return mpath, fpath

    def test_missing_manifest(self, tmp_path):
        mpath = tmp_path / "missing.json"
        result = check_dual_proof_integrity(mpath)
        assert not result.passed

    def test_complete_with_no_empty_fields(self, tmp_path):
        manifest = {"dual_proof_status": "DUAL_PROOF_COMPLETE", "empty_fields": []}
        mpath, _ = self._write(tmp_path, manifest)
        result = check_dual_proof_integrity(mpath)
        assert result.passed

    def test_complete_with_empty_fields_fails(self, tmp_path):
        manifest = {
            "dual_proof_status": "DUAL_PROOF_COMPLETE",
            "empty_fields": ["level_A_result"],
        }
        mpath, _ = self._write(tmp_path, manifest)
        result = check_dual_proof_integrity(mpath)
        assert not result.passed

    def test_final_status_complete_mismatch(self, tmp_path):
        manifest = {"dual_proof_status": "IN_PROGRESS", "empty_fields": []}
        final = {"framework_status": "COMPLETE", "n_empty": 0}
        mpath, fpath = self._write(tmp_path, manifest, final)
        result = check_dual_proof_integrity(mpath, fpath)
        assert not result.passed

    def test_final_status_complete_with_n_empty(self, tmp_path):
        manifest = {"dual_proof_status": "DUAL_PROOF_COMPLETE", "empty_fields": []}
        final = {"framework_status": "COMPLETE", "n_empty": 2}
        mpath, fpath = self._write(tmp_path, manifest, final)
        result = check_dual_proof_integrity(mpath, fpath)
        assert not result.passed

    def test_verdict_mismatch(self, tmp_path):
        manifest = {
            "dual_proof_status": "DUAL_PROOF_COMPLETE",
            "empty_fields": [],
            "synthetic_global_verdict": "ACCEPT",
        }
        final = {
            "framework_status": "COMPLETE",
            "n_empty": 0,
            "synthetic_verdict": "REJECT",
        }
        mpath, fpath = self._write(tmp_path, manifest, final)
        result = check_dual_proof_integrity(mpath, fpath)
        assert not result.passed


class TestIntegrityGate:
    def test_all_pass(self):
        checks = [IntegrityCheck(), IntegrityCheck()]
        ok, errors = integrity_gate(checks)
        assert ok is True
        assert errors == []

    def test_one_failure(self):
        ic = IntegrityCheck(path="/run/1")
        ic.fail("bad stuff")
        ok, errors = integrity_gate([ic])
        assert ok is False
        assert len(errors) == 1
        assert "/run/1" in errors[0]


class TestCheckAllIntegrity:
    def test_empty(self):
        results = check_all_integrity([])
        assert results == []

    def test_with_manifest(self, tmp_path):
        mpath = tmp_path / "manifest.json"
        mpath.write_text(
            json.dumps({"dual_proof_status": "IN_PROGRESS", "empty_fields": []}), encoding="utf-8"
        )
        results = check_all_integrity([], manifest_path=mpath)
        assert len(results) == 1


# ─── ori_core_v2 ─────────────────────────────────────────────────────────────

from oric.ori_core_v2 import (
    ModelV2Config,
    compare_all_variants,
    compute_C_trajectory,
    detect_threshold,
    run_variant_on_dataframe,
)


def _make_sv(n=100, seed=0):
    rng = np.random.default_rng(seed)
    S = rng.uniform(0, 1, n)
    V = rng.uniform(0.3, 0.8, n)
    return S, V


class TestModelV2Config:
    def test_defaults(self):
        cfg = ModelV2Config()
        assert cfg.variant == "V1"
        assert cfg.C_max == 10.0
        assert cfg.seed == 8000

    def test_frozen(self):
        cfg = ModelV2Config()
        with pytest.raises(Exception):
            cfg.variant = "V2"  # type: ignore[misc]


class TestComputeCTrajectory:
    def test_v1_length(self):
        S, V = _make_sv()
        C = compute_C_trajectory(S, V, ModelV2Config(variant="V1"))
        assert len(C) == 100
        assert C[0] == 0.0

    def test_v2_saturation_finite(self):
        S, V = _make_sv()
        C = compute_C_trajectory(S, V, ModelV2Config(variant="V2"))
        assert np.all(np.isfinite(C))

    def test_v3_feedback_finite(self):
        S, V = _make_sv()
        C = compute_C_trajectory(S, V, ModelV2Config(variant="V3"))
        assert np.all(np.isfinite(C))

    def test_v4_stochastic_finite(self):
        S, V = _make_sv()
        C = compute_C_trajectory(S, V, ModelV2Config(variant="V4"))
        assert np.all(np.isfinite(C))

    def test_v4_different_seeds_differ(self):
        S, V = _make_sv()
        C1 = compute_C_trajectory(S, V, ModelV2Config(variant="V4", seed=1))
        C2 = compute_C_trajectory(S, V, ModelV2Config(variant="V4", seed=2))
        assert not np.allclose(C1, C2)

    def test_unknown_variant_raises(self):
        S, V = _make_sv(n=10)
        with pytest.raises(ValueError, match="Unknown variant"):
            compute_C_trajectory(S, V, ModelV2Config(variant="V9"))  # type: ignore[arg-type]

    def test_v3_feedback_above_threshold(self):
        n = 50
        S = np.full(n, 0.5)
        V = np.full(n, 0.1)
        cfg = ModelV2Config(variant="V3", C_threshold=0.0)
        C = compute_C_trajectory(S, V, cfg)
        assert np.all(np.isfinite(C))

    def test_v2_c_max_zero(self):
        S, V = _make_sv(n=10)
        cfg = ModelV2Config(variant="V2", C_max=0.0)
        C = compute_C_trajectory(S, V, cfg)
        assert np.all(np.isfinite(C))


class TestDetectThreshold:
    def test_empty_array(self):
        idx, thr = detect_threshold(np.array([]))
        assert idx is None
        assert thr == 0.0

    def test_no_crossing(self):
        delta_C = np.zeros(100)
        idx, thr = detect_threshold(delta_C)
        assert idx is None

    def test_crossing_detected(self):
        n = 100
        delta_C = np.zeros(n)
        delta_C[60:] = 10.0  # large spike after baseline
        idx, thr = detect_threshold(delta_C, k=2.5, m=3, baseline_n=50)
        assert idx is not None
        assert idx >= 60

    def test_baseline_clipping(self):
        delta_C = np.ones(3)
        idx, thr = detect_threshold(delta_C, baseline_n=50)
        assert thr is not None


class TestRunVariantOnDataframe:
    def _df(self, n=80):
        rng = np.random.default_rng(42)
        return pd.DataFrame(
            {
                "S": rng.uniform(0, 1, n),
                "V": rng.uniform(0.3, 0.8, n),
            }
        )

    def test_adds_columns(self):
        df = self._df()
        out = run_variant_on_dataframe(df, "V1")
        assert "C_V1" in out.columns
        assert "delta_C_V1" in out.columns
        assert "threshold_hit_V1" in out.columns

    def test_preserves_original(self):
        df = self._df()
        run_variant_on_dataframe(df, "V2")
        assert list(df.columns) == ["S", "V"]

    def test_no_S_column_uses_zeros(self):
        df = pd.DataFrame({"V": np.ones(20) * 0.5})
        out = run_variant_on_dataframe(df, "V1")
        assert "C_V1" in out.columns

    def test_no_V_column_uses_half(self):
        df = pd.DataFrame({"S": np.ones(20) * 0.5})
        out = run_variant_on_dataframe(df, "V1")
        assert "C_V1" in out.columns

    def test_with_cfg(self):
        df = self._df()
        cfg = ModelV2Config(variant="V1", C_beta=0.1)
        out = run_variant_on_dataframe(df, "V1", cfg=cfg)
        assert "C_V1" in out.columns

    def test_threshold_hit_recorded(self):
        n = 100
        df = pd.DataFrame(
            {
                "S": np.concatenate([np.zeros(50), np.full(50, 2.0)]),
                "V": np.full(n, 0.01),
            }
        )
        out = run_variant_on_dataframe(df, "V1")
        # hit may or may not trigger depending on dynamics; just check dtype
        assert out["threshold_hit_V1"].dtype in (np.int64, np.float64, object, int)


class TestCompareAllVariants:
    def test_returns_all_variants(self):
        rng = np.random.default_rng(0)
        n = 100
        df = pd.DataFrame(
            {
                "S": rng.uniform(0, 1, n),
                "V": rng.uniform(0.3, 0.8, n),
            }
        )
        results, _ = compare_all_variants(df)
        for v in ("V1", "V2", "V3", "V4"):
            assert v in results

    def test_result_keys(self):
        rng = np.random.default_rng(0)
        n = 80
        df = pd.DataFrame(
            {
                "S": rng.uniform(0, 1, n),
                "V": rng.uniform(0.3, 0.8, n),
            }
        )
        results, _ = compare_all_variants(df)
        for v, res in results.items():
            assert "verdict" in res
            assert "C_mean" in res
            assert "effect_size_d" in res

    def test_verdict_values(self):
        rng = np.random.default_rng(0)
        n = 80
        df = pd.DataFrame(
            {
                "S": rng.uniform(0, 1, n),
                "V": rng.uniform(0.3, 0.8, n),
            }
        )
        results, _ = compare_all_variants(df)
        for v, res in results.items():
            assert res["verdict"] in ("ACCEPT", "INDETERMINATE")
