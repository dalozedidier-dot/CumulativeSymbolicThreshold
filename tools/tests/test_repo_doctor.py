"""Unit tests for tools/repo_doctor.py."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.repo_doctor import (
    check_contracts,
    check_ci_metrics,
    check_docs,
    run_all,
)


# ── check_contracts ───────────────────────────────────────────────────────────


def test_check_contracts_both_valid(tmp_path):
    fake_root = tmp_path
    contracts_dir = fake_root / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "POWER_CRITERIA.json").write_text('{"schema": "v1"}')
    (contracts_dir / "STABILITY_CRITERIA.json").write_text('{"max": 0.3}')

    with patch("tools.repo_doctor.ROOT", fake_root):
        results = check_contracts()

    levels = [lvl for lvl, _ in results]
    assert "ERROR" not in levels


def test_check_contracts_missing_power(tmp_path):
    fake_root = tmp_path
    contracts_dir = fake_root / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "STABILITY_CRITERIA.json").write_text('{"max": 0.3}')

    with patch("tools.repo_doctor.ROOT", fake_root):
        results = check_contracts()

    errors = [msg for lvl, msg in results if lvl == "ERROR"]
    assert any("POWER_CRITERIA" in e for e in errors)


def test_check_contracts_invalid_json(tmp_path):
    fake_root = tmp_path
    contracts_dir = fake_root / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "POWER_CRITERIA.json").write_text("not-json")
    (contracts_dir / "STABILITY_CRITERIA.json").write_text('{"ok": true}')

    with patch("tools.repo_doctor.ROOT", fake_root):
        results = check_contracts()

    errors = [msg for lvl, msg in results if lvl == "ERROR"]
    assert any("invalid json" in e.lower() or "invalid JSON" in e for e in errors)


# ── check_ci_metrics ─────────────────────────────────────────────────────────


def _write_runs_index(tmp_path: Path, rows: list[dict]) -> None:
    ci = tmp_path / "ci_metrics"
    ci.mkdir()
    path = ci / "runs_index.csv"
    fields = [
        "github_run_id", "run_dir_name", "dataset_id", "sector", "run_mode",
        "evidence_strength", "all_pass", "manifest_sha256",
        "stability_criteria_sha256", "commit_sha", "workflow_source",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_check_ci_metrics_clean(tmp_path):
    _write_runs_index(tmp_path, [
        {"github_run_id": "1", "run_dir_name": "ts1", "dataset_id": "qcc",
         "sector": "qcc", "run_mode": "full", "evidence_strength": "high",
         "all_pass": "True", "manifest_sha256": "a" * 64,
         "stability_criteria_sha256": "b" * 64, "commit_sha": "abc",
         "workflow_source": "QCC Canonical"}
    ])
    with patch("tools.repo_doctor.ROOT", tmp_path):
        results = check_ci_metrics()
    levels = [lvl for lvl, _ in results]
    assert "ERROR" not in levels
    assert "WARNING" not in levels


def test_check_ci_metrics_dirty_rows(tmp_path):
    _write_runs_index(tmp_path, [
        {"github_run_id": "1", "run_dir_name": "ts1", "dataset_id": "qcc",
         "sector": "unknown", "run_mode": "", "evidence_strength": "high",
         "all_pass": "True", "manifest_sha256": "a" * 64,
         "stability_criteria_sha256": "b" * 64, "commit_sha": "abc",
         "workflow_source": ""}
    ])
    with patch("tools.repo_doctor.ROOT", tmp_path):
        results = check_ci_metrics()
    warnings = [msg for lvl, msg in results if lvl == "WARNING"]
    assert any("sector=unknown" in w or "run_mode" in w for w in warnings)


def test_check_ci_metrics_missing_file(tmp_path):
    (tmp_path / "ci_metrics").mkdir()
    with patch("tools.repo_doctor.ROOT", tmp_path):
        results = check_ci_metrics()
    errors = [msg for lvl, msg in results if lvl == "ERROR"]
    assert any("runs_index.csv" in e for e in errors)


# ── check_docs ────────────────────────────────────────────────────────────────


def test_check_docs_present(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ORI_C_POINT_OF_TRUTH.md").write_text("# canonical")

    with patch("tools.repo_doctor.ROOT", tmp_path):
        results = check_docs()

    errors = [msg for lvl, msg in results if lvl == "ERROR"]
    assert not errors


def test_check_docs_missing(tmp_path):
    (tmp_path / "docs").mkdir()

    with patch("tools.repo_doctor.ROOT", tmp_path):
        results = check_docs()

    errors = [msg for lvl, msg in results if lvl == "ERROR"]
    assert any("ORI_C_POINT_OF_TRUTH" in e for e in errors)


def test_check_docs_redirect_stub_ok(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ORI_C_POINT_OF_TRUTH.md").write_text("# canonical")
    (tmp_path / "ORIC_POINT_OF_TRUTH.md").write_text(
        "This file is an alias redirect to docs/ORI_C_POINT_OF_TRUTH.md"
    )

    with patch("tools.repo_doctor.ROOT", tmp_path):
        results = check_docs()

    warnings = [msg for lvl, msg in results if lvl == "WARNING"]
    assert not any("duplicate" in w.lower() for w in warnings)


# ── run_all() ─────────────────────────────────────────────────────────────────


def test_run_all_returns_passed_key():
    report = run_all()
    assert "passed" in report
    assert isinstance(report["passed"], bool)


def test_run_all_returns_errors_and_warnings():
    report = run_all()
    assert "errors" in report
    assert "warnings" in report
    assert isinstance(report["errors"], list)
    assert isinstance(report["warnings"], list)
