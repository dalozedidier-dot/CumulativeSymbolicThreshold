"""test_sector_summary_verdict_alignment.py — Ticket 3.

Ensures summary.json["verdict"] is always derived from the canonical
verdict (verdict.json or verdict.txt) and never contradicts it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SECTOR_SHARED = _REPO_ROOT / "04_Code" / "sector" / "shared"
if str(_SECTOR_SHARED) not in sys.path:
    sys.path.insert(0, str(_SECTOR_SHARED))

from sector_panel_runner import _sync_summary_verdict


def _make_run_dir(tmp_path, summary_data, verdict_json=None, verdict_txt=None):
    """Create a fake run directory with the specified artefacts."""
    tables = tmp_path / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    (tables / "summary.json").write_text(
        json.dumps(summary_data), encoding="utf-8"
    )

    if verdict_json is not None:
        (tables / "verdict.json").write_text(
            json.dumps(verdict_json), encoding="utf-8"
        )

    if verdict_txt is not None:
        (tmp_path / "verdict.txt").write_text(verdict_txt, encoding="utf-8")


class TestSyncSummaryVerdict:
    """summary.json["verdict"] must always match the canonical verdict."""

    def test_summary_synced_to_verdict_json(self, tmp_path):
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT", "metric": 42},
            verdict_json={"verdict": "REJECT"},
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "REJECT"
        assert s["verdict_source"] == "verdict.json"

    def test_precheck_false_overrides_accept(self, tmp_path):
        """precheck_passed=false in verdict.json → summary cannot show ACCEPT."""
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT"},
            verdict_json={
                "verdict": "ACCEPT",
                "precheck_passed": False,
                "precheck_reason": "min_variance too low",
            },
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE"
        assert s["precheck_passed"] is False
        assert "precheck_passed=false" in s.get("verdict_override_reason", "")

    def test_precheck_true_keeps_accept(self, tmp_path):
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT"},
            verdict_json={"verdict": "ACCEPT", "precheck_passed": True},
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "ACCEPT"

    def test_fallback_to_verdict_txt(self, tmp_path):
        """When verdict.json is absent, verdict.txt is used."""
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT"},
            verdict_txt="INDETERMINATE\n",
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE"
        assert s["verdict_source"] == "verdict.txt"

    def test_all_verdict_values(self, tmp_path):
        """Sync works for ACCEPT, REJECT, and INDETERMINATE."""
        for verdict in ("ACCEPT", "REJECT", "INDETERMINATE"):
            run_dir = tmp_path / verdict.lower()
            run_dir.mkdir()
            _make_run_dir(
                run_dir,
                summary_data={"verdict": "wrong_value"},
                verdict_json={"verdict": verdict},
            )
            _sync_summary_verdict(run_dir)
            s = json.loads((run_dir / "tables" / "summary.json").read_text())
            assert s["verdict"] == verdict

    def test_indeterminate_precheck_preserved(self, tmp_path):
        """The precheck_reason from verdict.json propagates into summary."""
        reason = "indeterminate_precheck_failed:min_variance"
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT"},
            verdict_json={
                "verdict": "INDETERMINATE",
                "precheck_passed": False,
                "precheck_reason": reason,
            },
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "INDETERMINATE"
        assert s["precheck_reason"] == reason

    def test_no_summary_does_nothing(self, tmp_path):
        """No summary.json → nothing happens (no error)."""
        tables = tmp_path / "tables"
        tables.mkdir()
        (tables / "verdict.json").write_text(
            json.dumps({"verdict": "ACCEPT"}), encoding="utf-8"
        )
        _sync_summary_verdict(tmp_path)  # Should not raise

    def test_no_verdict_sources_does_nothing(self, tmp_path):
        """No verdict.json and no verdict.txt → summary untouched."""
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT", "extra": True},
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "ACCEPT"  # Untouched
        assert "verdict_source" not in s

    def test_preserves_other_summary_fields(self, tmp_path):
        """Sync must not destroy other fields in summary.json."""
        _make_run_dir(
            tmp_path,
            summary_data={"verdict": "ACCEPT", "dataset_id": "fred", "run_mode": "full"},
            verdict_json={"verdict": "REJECT"},
        )
        _sync_summary_verdict(tmp_path)
        s = json.loads((tmp_path / "tables" / "summary.json").read_text())
        assert s["verdict"] == "REJECT"
        assert s["dataset_id"] == "fred"
        assert s["run_mode"] == "full"
