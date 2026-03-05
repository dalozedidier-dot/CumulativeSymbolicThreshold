"""Unit tests for tools/enforce_output_contract.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.enforce_output_contract import _find_latest_run_dir, enforce


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_valid_run_dir(tmp_path: Path) -> Path:
    """Create a fully compliant run directory."""
    run_dir = tmp_path / "runs" / "20260101_000000"
    (run_dir / "tables").mkdir(parents=True)
    (run_dir / "contracts").mkdir(parents=True)
    (run_dir / "figures").mkdir(parents=True)

    summary = {"dataset_id": "test_ds", "run_mode": "full"}
    (run_dir / "tables" / "summary.json").write_text(json.dumps(summary))
    (run_dir / "tables" / "timeseries.csv").write_text("t,v\n0,1\n")
    (run_dir / "contracts" / "POWER_CRITERIA.json").write_text("{}")
    (run_dir / "figures" / "fig1.png").write_bytes(b"\x89PNG")
    (run_dir / "figures" / "fig2.png").write_bytes(b"\x89PNG")
    (run_dir / "manifest.json").write_text(json.dumps({"files": []}))
    return run_dir


# ── enforce() ────────────────────────────────────────────────────────────────


def test_enforce_valid_run_dir(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    passed, report = enforce(run_dir)
    assert passed is True
    assert report["errors"] == []


def test_enforce_missing_summary(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    (run_dir / "tables" / "summary.json").unlink()
    passed, report = enforce(run_dir)
    assert passed is False
    assert any("summary.json" in e for e in report["errors"])


def test_enforce_missing_contracts_dir(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    import shutil
    shutil.rmtree(run_dir / "contracts")
    passed, report = enforce(run_dir)
    assert passed is False
    assert any("contracts" in e for e in report["errors"])


def test_enforce_missing_figures_dir(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    import shutil
    shutil.rmtree(run_dir / "figures")
    passed, report = enforce(run_dir)
    assert passed is False
    assert any("figures" in e for e in report["errors"])


def test_enforce_missing_manifest(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    (run_dir / "manifest.json").unlink()
    passed, report = enforce(run_dir)
    assert passed is False
    assert any("manifest" in e.lower() for e in report["errors"])


def test_enforce_invalid_summary_json(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    (run_dir / "tables" / "summary.json").write_text("not-json")
    passed, report = enforce(run_dir)
    assert passed is False
    assert any("Invalid JSON" in e for e in report["errors"])


def test_enforce_missing_required_keys_warns(tmp_path):
    """Missing recommended keys in summary.json → warning, not error."""
    run_dir = _make_valid_run_dir(tmp_path)
    # summary without required_keys
    (run_dir / "tables" / "summary.json").write_text(json.dumps({"only_other": 1}))
    passed, report = enforce(run_dir)
    # Should still pass (required_keys generate warnings not errors)
    assert report["warnings"]


def test_enforce_no_csv_in_tables_warns(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    (run_dir / "tables" / "timeseries.csv").unlink()
    passed, report = enforce(run_dir)
    assert any("CSV" in w for w in report["warnings"])


def test_enforce_empty_contracts_dir_fails(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    # Remove all files from contracts
    for f in (run_dir / "contracts").iterdir():
        f.unlink()
    passed, report = enforce(run_dir)
    assert passed is False


def test_enforce_report_structure(tmp_path):
    run_dir = _make_valid_run_dir(tmp_path)
    passed, report = enforce(run_dir)
    assert "run_dir" in report
    assert "passed" in report
    assert "errors" in report
    assert "warnings" in report
    assert "checks" in report


# ── _find_latest_run_dir ─────────────────────────────────────────────────────


def test_find_latest_run_dir(tmp_path):
    out_root = tmp_path / "out"
    runs = out_root / "runs"
    (runs / "20260101_000000").mkdir(parents=True)
    (runs / "20260102_000000").mkdir(parents=True)
    latest = _find_latest_run_dir(out_root)
    assert latest.name == "20260102_000000"


def test_find_latest_run_dir_missing_runs(tmp_path):
    out_root = tmp_path / "out"
    out_root.mkdir()
    with pytest.raises(FileNotFoundError):
        _find_latest_run_dir(out_root)


def test_find_latest_run_dir_empty_runs(tmp_path):
    out_root = tmp_path / "out"
    (out_root / "runs").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        _find_latest_run_dir(out_root)
