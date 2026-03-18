"""test_dual_proof_manifest_fallback.py — Ticket 1.

Ensures that the synthetic branch of dual_proof_manifest can never stay
empty when the statistical gate is passed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from oric.proof_manifest import (
    DualProofManifest,
    build_dual_proof_manifest,
    _apply_synthetic_fallback,
)


class TestSyntheticFallback:
    """gate_passed=True + empty verdict/support → forced ACCEPT."""

    def test_gate_passed_empty_verdict_and_support(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="",
            synthetic_support_level="",
            synthetic_n_statistical_passed=95,
            fred_global_verdict="ACCEPT",
            fred_support_level="full_statistical_support",
            validation_verdict="ACCEPT",
            validation_test_detection_rate=0.90,
            validation_best_input="fred_monthly",
        )
        _apply_synthetic_fallback(m)
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_support_level == "full_statistical_support"

    def test_gate_passed_none_verdict_and_support(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict=None,
            synthetic_support_level=None,
            synthetic_n_statistical_passed=95,
        )
        _apply_synthetic_fallback(m)
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_support_level == "full_statistical_support"

    def test_gate_passed_unknown_verdict(self):
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="UNKNOWN",
            synthetic_support_level="",
            synthetic_n_statistical_passed=95,
        )
        _apply_synthetic_fallback(m)
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_support_level == "full_statistical_support"

    def test_gate_passed_already_accept_not_overwritten(self):
        """Already correct values must not be overwritten."""
        m = DualProofManifest(
            synthetic_gate_passed=True,
            synthetic_global_verdict="ACCEPT",
            synthetic_support_level="full_statistical_support",
            synthetic_n_statistical_passed=95,
        )
        _apply_synthetic_fallback(m)
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_support_level == "full_statistical_support"

    def test_gate_not_passed_no_fallback(self):
        """gate_passed=False → no fallback applied."""
        m = DualProofManifest(
            synthetic_gate_passed=False,
            synthetic_global_verdict="",
            synthetic_support_level="",
        )
        _apply_synthetic_fallback(m)
        assert m.synthetic_global_verdict == ""
        assert m.synthetic_support_level == ""

    def test_gate_none_no_fallback(self):
        """gate_passed=None → no fallback applied."""
        m = DualProofManifest(
            synthetic_gate_passed=None,
            synthetic_global_verdict="",
            synthetic_support_level="",
        )
        _apply_synthetic_fallback(m)
        assert m.synthetic_global_verdict == ""
        assert m.synthetic_support_level == ""


class TestFallbackInBuilder:
    """The fallback must be applied inside build_dual_proof_manifest."""

    def test_builder_applies_fallback(self, tmp_path):
        tables = tmp_path / "tables"
        tables.mkdir()
        summary = {
            "gate_passed": True,
            "protocol_verdict": "",
            "support_level": "",
            "n_statistical_passed": 95,
            "discrimination_metrics": {
                "sensitivity": 0.96,
                "specificity": 0.97,
            },
        }
        (tables / "validation_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        m = build_dual_proof_manifest(synthetic_dir=tmp_path)
        # Fallback must have kicked in
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_support_level == "full_statistical_support"
        assert m.synthetic_gate_passed is True

    def test_builder_completeness_after_fallback(self, tmp_path):
        """After fallback, the manifest should be complete if all other fields are ok."""
        tables = tmp_path / "tables"
        tables.mkdir()
        summary = {
            "gate_passed": True,
            "protocol_verdict": "",
            "support_level": "",
            "n_statistical_passed": 95,
        }
        (tables / "validation_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )

        fred_dir = tmp_path / "fred"
        fred_tables = fred_dir / "tables"
        fred_tables.mkdir(parents=True)
        (fred_tables / "validation_summary.json").write_text(
            json.dumps({
                "protocol_verdict": "ACCEPT",
                "support_level": "full_statistical_support",
            }),
            encoding="utf-8",
        )

        val_dir = tmp_path / "val"
        val_tables = val_dir / "tables"
        val_tables.mkdir(parents=True)
        (val_tables / "validation_summary.json").write_text(
            json.dumps({
                "protocol_verdict": "ACCEPT",
                "test_det_rate": 0.95,
                "best_input": "fred_monthly",
                "discrimination_metrics": {
                    "sensitivity": 0.92,
                    "specificity": 0.88,
                    "fisher_p_value": 1e-20,
                },
            }),
            encoding="utf-8",
        )

        m = build_dual_proof_manifest(
            synthetic_dir=tmp_path,
            fred_dir=fred_dir,
            validation_dir=val_dir,
        )
        assert m.synthetic_global_verdict == "ACCEPT"
        assert m.synthetic_support_level == "full_statistical_support"
        assert m.dual_proof_status == "DUAL_PROOF_COMPLETE"
