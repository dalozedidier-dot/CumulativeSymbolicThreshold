"""test_artifact_consistency_audit.py — Ticket 4.

Tests the nightly artifact consistency audit tool.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from audit_artifact_consistency import (
    run_audit,
    check_summary_vs_verdict,
    check_synthetic_consistency,
    check_fred_consistency,
    check_forbidden_empty_fields,
    AuditReport,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TestConsistentBundle:
    """A fully consistent bundle should produce PASS."""

    def test_clean_bundle_passes(self, tmp_path):
        manifest = {
            "dual_proof_status": "DUAL_PROOF_COMPLETE",
            "synthetic_gate_passed": True,
            "synthetic_global_verdict": "ACCEPT",
            "synthetic_support_level": "full_statistical_support",
            "fred_global_verdict": "ACCEPT",
            "fred_support_level": "full_statistical_support",
            "validation_verdict": "ACCEPT",
            "empty_fields": [],
            "inconsistencies": [],
        }
        final = {
            "framework_status": "COMPLETE",
            "n_empty": 0,
            "synthetic_verdict": "ACCEPT",
            "real_data_verdict": "ACCEPT",
            "validation_verdict": "ACCEPT",
        }
        _write_json(tmp_path / "dual_proof_manifest.json", manifest)
        _write_json(tmp_path / "final_status.json", final)

        # Add a valid run dir
        run_dir = tmp_path / "run1"
        _write_json(run_dir / "tables" / "summary.json", {"verdict": "ACCEPT"})
        _write_json(run_dir / "tables" / "verdict.json", {"verdict": "ACCEPT"})
        (run_dir / "verdict.txt").write_text("ACCEPT\n", encoding="utf-8")

        report = run_audit(tmp_path)
        assert report.status == "PASS"
        assert report.n_errors == 0


class TestInconsistentBundle:
    """Inconsistent bundles should produce FAIL."""

    def test_manifest_final_status_mismatch(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_INCOMPLETE",
            "synthetic_gate_passed": False,
        })
        _write_json(tmp_path / "final_status.json", {
            "framework_status": "COMPLETE",
            "n_empty": 0,
        })
        report = run_audit(tmp_path, run_dirs=[])
        assert report.status == "FAIL"
        assert any("manifest" in f.message.lower() or "COMPLETE" in f.message
                    for f in report.findings)

    def test_summary_verdict_mismatch(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_INCOMPLETE",
        })
        _write_json(tmp_path / "final_status.json", {
            "framework_status": "INCOMPLETE",
        })

        run_dir = tmp_path / "run1"
        _write_json(run_dir / "tables" / "summary.json", {"verdict": "ACCEPT"})
        _write_json(run_dir / "tables" / "verdict.json", {"verdict": "REJECT"})
        (run_dir / "verdict.txt").write_text("REJECT\n", encoding="utf-8")

        report = run_audit(tmp_path)
        assert report.status == "FAIL"
        assert any("summary" in f.check for f in report.findings)

    def test_synthetic_gate_true_empty_verdict(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_INCOMPLETE",
            "synthetic_gate_passed": True,
            "synthetic_global_verdict": "",
            "synthetic_support_level": "",
        })
        report = AuditReport()
        check_synthetic_consistency(tmp_path, report)
        assert report.status == "FAIL"
        assert report.n_errors >= 1

    def test_fred_accept_no_support(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_INCOMPLETE",
            "fred_global_verdict": "ACCEPT",
            "fred_support_level": "",
        })
        report = AuditReport()
        check_fred_consistency(tmp_path, report)
        assert report.status == "FAIL"

    def test_complete_but_has_empty_fields(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_COMPLETE",
            "empty_fields": ["validation.verdict"],
            "inconsistencies": [],
        })
        report = AuditReport()
        check_forbidden_empty_fields(tmp_path, report)
        assert report.status == "FAIL"

    def test_precheck_false_accept_conflict(self, tmp_path):
        run_dir = tmp_path / "run_precheck"
        _write_json(run_dir / "tables" / "summary.json", {"verdict": "ACCEPT"})
        _write_json(run_dir / "tables" / "verdict.json", {
            "verdict": "ACCEPT",
            "precheck_passed": False,
        })
        report = AuditReport()
        check_summary_vs_verdict(run_dir, report)
        assert report.status == "FAIL"
        assert any("precheck" in f.check for f in report.findings)


class TestMissingFiles:
    """Missing files should produce appropriate errors."""

    def test_no_manifest(self, tmp_path):
        _write_json(tmp_path / "final_status.json", {"framework_status": "INCOMPLETE"})
        report = run_audit(tmp_path, run_dirs=[])
        assert report.status == "FAIL"
        assert any("manifest" in f.check for f in report.findings)

    def test_no_final_status(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_INCOMPLETE",
        })
        report = run_audit(tmp_path, run_dirs=[])
        assert report.status == "FAIL"
        assert any("final_status" in f.check for f in report.findings)


class TestReportOutput:
    """The report should be properly structured."""

    def test_report_dict_structure(self, tmp_path):
        _write_json(tmp_path / "dual_proof_manifest.json", {
            "dual_proof_status": "DUAL_PROOF_INCOMPLETE",
        })
        _write_json(tmp_path / "final_status.json", {"framework_status": "INCOMPLETE"})
        report = run_audit(tmp_path, run_dirs=[])
        d = report.to_dict()
        assert "status" in d
        assert "n_errors" in d
        assert "n_warnings" in d
        assert "findings" in d
        assert isinstance(d["findings"], list)
