"""test_final_gate_proof_dimensions.py — Ticket 2.

Ensures that the final gate reads proof_dimensions canonically
and fails explicitly on incomplete or invalid schema.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from oric.proof_manifest import (
    DualProofManifest,
    build_final_status,
    read_proof_dimensions,
    FinalGateError,
    _extract_proof_dimensions,
)


class TestBuildFinalStatusCanonical:
    """final_status must read ONLY through proof_dimensions."""

    def test_complete_manifest_produces_complete_status(self):
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

        assert fs["schema"] == "oric.final_status.v2"
        assert fs["framework_status"] == "COMPLETE"
        assert "proof_dimensions" in fs

        dims = fs["proof_dimensions"]
        assert dims["synthetic"]["global_verdict"] == "ACCEPT"
        assert dims["real_data_fred"]["global_verdict"] == "ACCEPT"
        assert dims["real_data_validation_protocol"]["verdict"] == "ACCEPT"
        assert fs["incompleteness_reason"] is None

    def test_missing_dimension_verdict_is_incomplete(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict=None,  # Missing!
            fred_support_level=None,
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
        )
        m.check_completeness()
        fs = build_final_status(m)

        assert fs["framework_status"] == "INCOMPLETE"
        assert fs["incompleteness_reason"] == "one_or_more_dimension_verdicts_missing"

    def test_not_all_accept_is_incomplete(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="REJECT",
            fred_support_level="rejected",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.95,
            validation_best_input="fred_monthly",
        )
        m.check_completeness()
        fs = build_final_status(m)

        assert fs["framework_status"] == "INCOMPLETE"
        assert fs["incompleteness_reason"] == "not_all_accept"

    def test_proof_dimensions_structure(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="INDETERMINATE",
            validation_test_detection_rate=0.60,
            validation_best_input="fred_monthly",
            validation_sensitivity=0.60,
            validation_specificity=0.70,
            validation_fisher_p=0.05,
        )
        m.check_completeness()
        dims = _extract_proof_dimensions(m)

        assert set(dims.keys()) == {
            "synthetic", "real_data_fred", "real_data_validation_protocol"
        }
        assert dims["synthetic"]["gate_passed"] is True
        assert dims["real_data_validation_protocol"]["sensitivity"] == 0.60


class TestReadProofDimensions:
    """read_proof_dimensions must validate and reject bad schemas."""

    def test_valid_manifest_with_proof_dimensions(self):
        data = {
            "proof_dimensions": {
                "synthetic": {"global_verdict": "ACCEPT", "gate_passed": True,
                              "support_level": "full_statistical_support",
                              "n_statistical_passed": 95},
                "real_data_fred": {"global_verdict": "ACCEPT",
                                   "support_level": "full_statistical_support"},
                "real_data_validation_protocol": {
                    "verdict": "ACCEPT", "test_detection_rate": 0.95,
                    "best_input": "fred_monthly", "sensitivity": 0.92,
                    "specificity": 0.88, "fisher_p": 1e-20,
                },
            }
        }
        dims = read_proof_dimensions(data)
        assert dims["synthetic"]["global_verdict"] == "ACCEPT"

    def test_flat_manifest_reconstructed(self):
        """Flat DualProofManifest dict should be reconstructed."""
        data = {
            "synthetic_gate_passed": True,
            "synthetic_global_verdict": "ACCEPT",
            "synthetic_support_level": "full_statistical_support",
            "synthetic_n_statistical_passed": 95,
            "fred_global_verdict": "ACCEPT",
            "fred_support_level": "full_statistical_support",
            "validation_verdict": "ACCEPT",
            "validation_test_detection_rate": 0.95,
            "validation_best_input": "fred_monthly",
            "validation_sensitivity": 0.92,
            "validation_specificity": 0.88,
            "validation_fisher_p": 1e-20,
        }
        dims = read_proof_dimensions(data)
        assert dims["synthetic"]["global_verdict"] == "ACCEPT"
        assert dims["real_data_fred"]["global_verdict"] == "ACCEPT"
        assert dims["real_data_validation_protocol"]["verdict"] == "ACCEPT"

    def test_empty_dict_raises_error(self):
        with pytest.raises(FinalGateError, match="missing.*proof_dimensions"):
            read_proof_dimensions({})

    def test_missing_dimension_raises_error(self):
        data = {
            "proof_dimensions": {
                "synthetic": {"global_verdict": "ACCEPT"},
                # real_data_fred missing
                "real_data_validation_protocol": {"verdict": "ACCEPT"},
            }
        }
        with pytest.raises(FinalGateError, match="Missing required.*real_data_fred"):
            read_proof_dimensions(data)

    def test_none_verdict_raises_error(self):
        data = {
            "proof_dimensions": {
                "synthetic": {"global_verdict": None},
                "real_data_fred": {"global_verdict": "ACCEPT"},
                "real_data_validation_protocol": {"verdict": "ACCEPT"},
            }
        }
        with pytest.raises(FinalGateError, match="synthetic.*None"):
            read_proof_dimensions(data)

    def test_empty_string_verdict_raises_error(self):
        data = {
            "proof_dimensions": {
                "synthetic": {"global_verdict": "ACCEPT"},
                "real_data_fred": {"global_verdict": ""},
                "real_data_validation_protocol": {"verdict": "ACCEPT"},
            }
        }
        with pytest.raises(FinalGateError, match="real_data_fred.*empty"):
            read_proof_dimensions(data)

    def test_old_schema_without_flat_fields_raises(self):
        """An old schema dict with no useful fields must error."""
        data = {"version": "old", "some_field": 42}
        with pytest.raises(FinalGateError):
            read_proof_dimensions(data)
