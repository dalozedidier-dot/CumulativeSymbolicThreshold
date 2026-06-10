"""Third coverage boost: _entrypoints, decidability diagnostics, frozen_params,
integrity OSError path, placebo edge cases, proof_levels, proof_manifest builder
fallbacks, proof_package optional blocs.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

# ─── _entrypoints ────────────────────────────────────────────────────────────

from oric import _entrypoints


class TestEntrypoints:
    def test_run_all_invokes_runpy(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            _entrypoints.runpy,
            "run_path",
            lambda path, run_name=None: calls.append((path, run_name)),
        )
        _entrypoints.run_all()
        assert len(calls) == 1
        path, run_name = calls[0]
        assert path.endswith("run_all.py")
        assert run_name == "__main__"

    def test_run_all_tests_invokes_runpy(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            _entrypoints.runpy,
            "run_path",
            lambda path, run_name=None: calls.append((path, run_name)),
        )
        _entrypoints.run_all_tests()
        assert len(calls) == 1
        path, run_name = calls[0]
        assert path.endswith("run_all_tests.py")
        assert run_name == "__main__"


# ─── decidability ────────────────────────────────────────────────────────────

from oric.decidability import (
    AdaptedPrechecks,
    check_precheck,
    compute_decidability,
)


class TestComputeDecidabilityDiagnostics:
    def test_diagnostic_means_computed(self):
        runs = [
            {
                "verdict": "DETECTED",
                "c_variance": 1.0,
                "n_unique_c": 10,
                "n_rows": 100,
            },
            {
                "verdict": "NOT_DETECTED",
                "c_variance": 3.0,
                "n_unique_c": 20,
                "n_rows": 200,
            },
        ]
        m = compute_decidability(runs, condition="test")
        assert m.mean_c_variance == 2.0
        assert m.mean_n_unique_c == 15.0
        assert m.mean_series_length == 150.0


class TestAdaptedPrechecksPlaceboRegime:
    def test_placebo_regime_values(self):
        p = AdaptedPrechecks.for_regime("placebo")
        assert p.min_points_per_segment == 60
        assert p.min_unique_values_C == 4
        assert p.min_variance_C == 1e-12


class TestCheckPrecheckFailures:
    def test_min_points_post_fails(self):
        prechecks = AdaptedPrechecks(min_points_per_segment=10)
        c_pre = np.linspace(0, 1, 20)
        c_post = np.linspace(0, 1, 5)
        passed, reason = check_precheck(c_pre, c_post, prechecks)
        assert not passed
        assert "min_points_post" in reason

    def test_nan_fraction_fails(self):
        prechecks = AdaptedPrechecks(min_points_per_segment=10, max_nan_frac=0.05)
        c_pre = np.linspace(0, 1, 100)
        c_pre[:50] = np.nan
        c_post = np.linspace(0, 1, 100)
        passed, reason = check_precheck(c_pre, c_post, prechecks)
        assert not passed
        assert "nan_frac_pre" in reason

    def test_min_variance_fails(self):
        prechecks = AdaptedPrechecks(min_points_per_segment=10, min_variance_C=1e-10)
        # Many unique values but near-zero variance
        c_pre = np.linspace(0.0, 1e-8, 100)
        c_post = np.linspace(0.0, 1e-8, 100)
        passed, reason = check_precheck(c_pre, c_post, prechecks)
        assert not passed
        assert "min_variance_pre" in reason


# ─── frozen_params ───────────────────────────────────────────────────────────

from oric.frozen_params import FROZEN_PARAMS, FrozenValidationParams, load_frozen_params


class TestLoadFrozenParams:
    def test_missing_file_returns_singleton(self, tmp_path):
        params = load_frozen_params(tmp_path / "missing.json")
        assert params is FROZEN_PARAMS

    def test_roundtrip_from_file(self, tmp_path):
        p = tmp_path / "params.json"
        FROZEN_PARAMS.save(p)
        loaded = load_frozen_params(p)
        assert isinstance(loaded, FrozenValidationParams)
        assert loaded == FROZEN_PARAMS

    def test_unknown_keys_ignored(self, tmp_path):
        p = tmp_path / "params.json"
        data = FROZEN_PARAMS.to_dict()
        data["bogus_key"] = 123
        data["alpha"] = 0.05
        p.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_frozen_params(p)
        assert loaded.alpha == 0.05
        assert not hasattr(loaded, "bogus_key")


# ─── integrity OSError path ──────────────────────────────────────────────────

from oric.integrity import _read_text_safe


class TestReadTextSafeOSError:
    def test_directory_path_returns_none(self, tmp_path):
        # read_text on a directory raises IsADirectoryError (an OSError)
        d = tmp_path / "adir"
        d.mkdir()
        assert _read_text_safe(d) is None


# ─── placebo edge cases ──────────────────────────────────────────────────────

from oric.placebo import (
    PlaceboBatteryResult,
    make_block_shuffle,
    make_phase_randomize,
    make_proxy_remap,
)


class TestPhaseRandomizeEdgeCases:
    def test_short_series_returned_unchanged(self):
        # n < 4 → series is copied verbatim, no FFT applied
        df = pd.DataFrame({"O": [1.0, 2.0, 3.0]})
        out, spec = make_phase_randomize(df, seed=1)
        assert spec.strategy == "phase_randomize"
        assert np.allclose(out["O"].to_numpy(), [1.0, 2.0, 3.0])

    def test_all_nan_column_skipped(self):
        df = pd.DataFrame(
            {
                "O": np.full(16, np.nan),
                "R": np.sin(np.arange(16, dtype=float)),
            }
        )
        out, _ = make_phase_randomize(df, seed=2)
        # All-NaN column is left untouched
        assert out["O"].isna().all()
        # Numeric column was actually randomized
        assert not np.allclose(out["R"].to_numpy(), df["R"].to_numpy())


class TestProxyRemapEdgeCases:
    def test_fewer_than_two_proxy_columns_noop(self):
        df = pd.DataFrame({"O": np.arange(10, dtype=float)})
        out, spec = make_proxy_remap(df, seed=3)
        assert spec.strategy == "proxy_remap"
        assert np.array_equal(out["O"].to_numpy(), df["O"].to_numpy())

    def test_identity_permutation_retried(self):
        # Find a seed whose FIRST 2-element permutation is identity,
        # forcing the retry loop to run at least once.
        seed = next(
            s for s in range(200) if np.random.default_rng(s).permutation(2).tolist() == [0, 1]
        )
        df = pd.DataFrame(
            {
                "O": np.arange(10, dtype=float),
                "R": np.arange(10, dtype=float) * 10,
            }
        )
        out, _ = make_proxy_remap(df, seed=seed, proxy_columns=["O", "R"])
        # The final permutation must NOT be identity: columns are swapped
        assert np.array_equal(out["O"].to_numpy(), df["R"].to_numpy())
        assert np.array_equal(out["R"].to_numpy(), df["O"].to_numpy())


class TestBlockShuffleRemainder:
    def test_remainder_block_kept(self):
        # n=23, block_size=5 → 4 full blocks + remainder block of 3 rows
        df = pd.DataFrame({"O": np.arange(23, dtype=float)})
        out, spec = make_block_shuffle(df, seed=4, block_size=5)
        assert spec.strategy == "block_shuffle"
        assert len(out) == 23
        # All original values are preserved, just reordered
        assert sorted(out["O"].tolist()) == list(map(float, range(23)))


class TestPlaceboBatteryResultDefaults:
    def test_per_strategy_defaults_to_empty_list(self):
        r = PlaceboBatteryResult()
        assert r.per_strategy == []
        assert r.to_dict()["per_strategy"] == []


# ─── proof_levels ────────────────────────────────────────────────────────────

from oric.proof_levels import (
    DatasetEvidence,
    build_proof_level_summary,
    classify_evidence_level,
)


class TestLevelBAdequatePower:
    def test_adequate_power_level_b_very_low_risk(self):
        # n_rows >= 200 (adequate power) but causal tests unavailable → not A.
        # All Level B criteria met → level B, adequate power → very_low risk.
        ev = classify_evidence_level(
            dataset_id="ds1",
            n_rows=300,
            verdict="ACCEPT",
            precheck_passed=True,
            causal_tests_available=False,
        )
        assert ev.level == "B"
        assert ev.power_class == "adequate"
        assert ev.overinterpretation_risk == "very_low"
        assert ev.limitation_notes == []


class TestLevelAVerdictAggregation:
    def _ev(self, verdict):
        return DatasetEvidence(dataset_id=f"ds_{verdict}", level="A", verdict=verdict)

    def test_reject_among_level_a(self):
        s = build_proof_level_summary([self._ev("ACCEPT"), self._ev("REJECT")])
        assert not s.level_a_all_accept
        assert s.level_a_verdict == "REJECT"

    def test_indeterminate_among_level_a(self):
        s = build_proof_level_summary([self._ev("ACCEPT"), self._ev("INDETERMINATE")])
        assert not s.level_a_all_accept
        assert s.level_a_verdict == "INDETERMINATE"


# ─── proof_manifest ──────────────────────────────────────────────────────────

from oric.proof_manifest import (
    DualProofManifest,
    _read_json,
    _safe_float,
    build_dual_proof_manifest,
)


def _write_summary(base, payload):
    tables = base / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "validation_summary.json").write_text(json.dumps(payload), encoding="utf-8")
    return base


class TestManifestSpecificityInconsistency:
    def test_accept_with_low_specificity_flagged(self):
        m = DualProofManifest(
            validation_verdict="ACCEPT",
            validation_sensitivity=0.95,
            validation_specificity=0.50,
        )
        m.check_completeness()
        assert any("specificity" in s for s in m.inconsistencies)
        assert m.dual_proof_status == "DUAL_PROOF_INCOMPLETE"


class TestReadJsonAndSafeFloat:
    def test_read_json_invalid_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert _read_json(p) is None

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_unparseable(self):
        assert _safe_float("not_a_number") is None
        assert _safe_float([1, 2]) is None

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) is None

    def test_safe_float_valid(self):
        assert _safe_float("0.5") == 0.5


class TestBuildManifestSyntheticFallbacks:
    def test_gate_from_verdict_details(self, tmp_path):
        d = _write_summary(
            tmp_path / "syn",
            {
                "verdict_details": {
                    "protocol_verdict": "ACCEPT",
                    "sensitivity": 0.9,
                    "specificity": 0.85,
                },
                "discrimination_metrics": {"confusion_matrix": {"TP": 8, "TN": 7}},
            },
        )
        m = build_dual_proof_manifest(synthetic_dir=d)
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_gate_passed is True
        assert m.synthetic_support_level == "full_statistical_support"
        assert m.synthetic_n_statistical_passed == 15

    def test_support_level_rejected(self, tmp_path):
        d = _write_summary(tmp_path / "syn", {"protocol_verdict": "REJECT"})
        m = build_dual_proof_manifest(synthetic_dir=d)
        assert m.synthetic_support_level == "rejected"

    def test_support_level_indeterminate(self, tmp_path):
        d = _write_summary(tmp_path / "syn", {"protocol_verdict": "INDETERMINATE"})
        m = build_dual_proof_manifest(synthetic_dir=d)
        assert m.synthetic_support_level == "indeterminate"


class TestBuildManifestFredFallbacks:
    def test_support_level_from_accept(self, tmp_path):
        d = _write_summary(tmp_path / "fred", {"protocol_verdict": "ACCEPT"})
        m = build_dual_proof_manifest(fred_dir=d)
        assert m.fred_support_level == "full_statistical_support"

    def test_support_level_from_reject(self, tmp_path):
        d = _write_summary(tmp_path / "fred", {"protocol_verdict": "REJECT"})
        m = build_dual_proof_manifest(fred_dir=d)
        assert m.fred_support_level == "rejected"

    def test_support_level_indeterminate(self, tmp_path):
        d = _write_summary(tmp_path / "fred", {"protocol_verdict": "WEIRD"})
        m = build_dual_proof_manifest(fred_dir=d)
        assert m.fred_support_level == "indeterminate"

    def test_verdict_txt_fallback(self, tmp_path):
        d = tmp_path / "fred"
        d.mkdir()
        (d / "verdict.txt").write_text("ACCEPT\n", encoding="utf-8")
        m = build_dual_proof_manifest(fred_dir=d)
        assert m.fred_global_verdict == "ACCEPT"
        assert m.fred_support_level is None


# ─── proof_package ───────────────────────────────────────────────────────────

from oric.decidability import DecidabilityMetrics
from oric.integrity import IntegrityCheck
from oric.proof_levels import ProofLevelSummary
from oric.proof_package import ProofPackage, build_proof_package


class TestProofPackageComputeOverall:
    def test_partial_when_only_bloc1_and_bloc2_pass(self):
        pkg = ProofPackage()
        pkg.bloc1_contractual.integrity_passed = True
        pkg.bloc1_contractual.manifest_complete = True
        pkg.bloc2_discriminant.discrimination_passes = True
        pkg.bloc3_robustness.robustness_passes = False
        pkg.compute_overall()
        assert pkg.overall_verdict == "PARTIAL"
        assert pkg.bloc_verdicts["bloc3_robustness"] == "FAIL"


class TestBuildProofPackageOptionalBlocs:
    def _manifest(self):
        m = DualProofManifest()
        m.check_completeness()
        return m

    def test_integrity_checks_recorded(self):
        chk = IntegrityCheck(path="run1")
        chk.fail("missing verdict.txt")
        pkg = build_proof_package(self._manifest(), integrity_checks=[chk])
        assert pkg.bloc1_contractual.integrity_passed is False
        assert pkg.bloc1_contractual.n_integrity_errors == 1
        assert "[run1] missing verdict.txt" in pkg.bloc1_contractual.integrity_errors

    def test_condition_decidability_builds_report(self):
        decid = {
            "test": DecidabilityMetrics(condition="test", detection_rate=0.9),
            "stable": DecidabilityMetrics(condition="stable", detection_rate=0.1),
            # "placebo" omitted on purpose: exercises default factory branch
        }
        pkg = build_proof_package(self._manifest(), condition_decidability=decid)
        b2 = pkg.bloc2_discriminant
        assert b2.test_detection_rate == 0.9
        assert b2.stable_detection_rate == 0.1
        assert b2.placebo_detection_rate == 0.0
        assert "overall" in b2.decidability_report

    def test_placebo_battery_recorded(self):
        battery = {"battery_passes": True, "n_strategies": 5}
        pkg = build_proof_package(self._manifest(), placebo_battery_result=battery)
        assert pkg.bloc2_discriminant.placebo_battery == battery

    def test_replication_info_all_true_passes(self):
        info = {
            "independent": True,
            "external_data": True,
            "frozen_protocol": True,
            "no_retuning": True,
        }
        pkg = build_proof_package(self._manifest(), replication_info=info)
        assert pkg.bloc4_external.external_passes is True
        assert pkg.bloc4_external.replication_details == info

    def test_replication_info_partial_fails(self):
        info = {"independent": True}
        pkg = build_proof_package(self._manifest(), replication_info=info)
        assert pkg.bloc4_external.external_passes is False

    def test_proof_levels_included(self):
        summary = ProofLevelSummary(n_level_a=1)
        pkg = build_proof_package(self._manifest(), proof_levels=summary)
        assert pkg.proof_levels["n_level_a"] == 1
