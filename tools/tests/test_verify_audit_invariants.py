"""Unit tests for tools/verify_audit_invariants.py."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.verify_audit_invariants import (
    check_contracts,
    check_manifest,
    check_stability,
    check_stability_reflects_contract,
    verify,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_run_dir(tmp_path: Path) -> Path:
    """Create a minimal valid run directory for use in tests."""
    run_dir = tmp_path / "runs" / "20260101_000000"
    for sub in ("contracts", "tables", "figures", "stability"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    # Contracts
    power = {"schema": "qcc.power_criteria.v1", "thresholds": {"high": {"total_points": 200}}}
    stability_criteria = {"max_relative_variation": 0.305, "min_resample_found_rate": 0.5}
    power_bytes = json.dumps(power).encode()
    stability_bytes = json.dumps(stability_criteria).encode()
    (run_dir / "contracts" / "POWER_CRITERIA.json").write_bytes(power_bytes)
    (run_dir / "contracts" / "STABILITY_CRITERIA.json").write_bytes(stability_bytes)

    # Stability summary (criteria_sha and matching threshold)
    criteria_sha = _sha256(stability_bytes)
    stability_summary = {
        "criteria_sha256": criteria_sha,
        "stability_check": {
            "all_pass": True,
            "checks": {
                "relative_variation": {"threshold": 0.305, "value": 0.1, "pass": True}
            },
        },
    }
    (run_dir / "stability" / "stability_summary.json").write_text(
        json.dumps(stability_summary), encoding="utf-8"
    )

    # Tables
    summary = {"dataset_id": "test_ds", "sector": "qcc", "run_mode": "full"}
    summary_bytes = json.dumps(summary).encode()
    (run_dir / "tables" / "summary.json").write_bytes(summary_bytes)

    # Figures placeholder
    fig_bytes = b"placeholder"
    (run_dir / "figures" / "placeholder.txt").write_bytes(fig_bytes)

    # Build manifest
    files = [
        {"path": "contracts/POWER_CRITERIA.json", "sha256": _sha256(power_bytes)},
        {"path": "contracts/STABILITY_CRITERIA.json", "sha256": _sha256(stability_bytes)},
        {"path": "tables/summary.json", "sha256": _sha256(summary_bytes)},
        {"path": "figures/placeholder.txt", "sha256": _sha256(fig_bytes)},
        {
            "path": "stability/stability_summary.json",
            "sha256": _sha256(
                (run_dir / "stability" / "stability_summary.json").read_bytes()
            ),
        },
    ]
    manifest = {"files": files, "manifest_sha256": "abc123"}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return run_dir


# ── check_contracts ───────────────────────────────────────────────────────────

def test_check_contracts_missing(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    errors = check_contracts(run_dir)
    assert any("POWER_CRITERIA" in e for e in errors)
    assert any("STABILITY_CRITERIA" in e for e in errors)


def test_check_contracts_present(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "contracts").mkdir(parents=True)
    (run_dir / "contracts" / "POWER_CRITERIA.json").write_text("{}")
    (run_dir / "contracts" / "STABILITY_CRITERIA.json").write_text("{}")
    errors = check_contracts(run_dir)
    assert errors == []


# ── check_stability ───────────────────────────────────────────────────────────

def test_check_stability_missing(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    errors = check_stability(run_dir, require_stability=True)
    assert any("stability_summary" in e for e in errors)


def test_check_stability_skipped_when_not_required(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    errors = check_stability(run_dir, require_stability=False)
    assert errors == []


def test_check_stability_present(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "stability").mkdir(parents=True)
    (run_dir / "stability" / "stability_summary.json").write_text("{}")
    errors = check_stability(run_dir, require_stability=True)
    assert errors == []


# ── check_stability_reflects_contract ────────────────────────────────────────

def test_stability_reflects_contract_both_absent(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    errors = check_stability_reflects_contract(run_dir)
    assert errors == []


def test_stability_reflects_contract_valid(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    errors = check_stability_reflects_contract(run_dir)
    assert errors == []


def test_stability_reflects_contract_sha_mismatch(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    # Tamper: write a wrong sha into stability_summary
    ss_path = run_dir / "stability" / "stability_summary.json"
    ss = json.loads(ss_path.read_text())
    ss["criteria_sha256"] = "0" * 64  # wrong sha
    ss_path.write_text(json.dumps(ss))
    errors = check_stability_reflects_contract(run_dir)
    assert any("criteria_sha256 mismatch" in e for e in errors)


def test_stability_reflects_contract_threshold_mismatch(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    ss_path = run_dir / "stability" / "stability_summary.json"
    ss = json.loads(ss_path.read_text())
    # Use wrong threshold
    ss["stability_check"]["checks"]["relative_variation"]["threshold"] = 0.999
    ss_path.write_text(json.dumps(ss))
    errors = check_stability_reflects_contract(run_dir)
    assert any("threshold mismatch" in e.lower() for e in errors)


def test_stability_reflects_contract_invalid_criteria_json(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    (run_dir / "contracts" / "STABILITY_CRITERIA.json").write_text("not-json")
    errors = check_stability_reflects_contract(run_dir)
    assert any("Cannot parse STABILITY_CRITERIA" in e for e in errors)


def test_stability_reflects_contract_invalid_summary_json(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    (run_dir / "stability" / "stability_summary.json").write_text("not-json")
    errors = check_stability_reflects_contract(run_dir)
    assert any("Cannot parse stability_summary" in e for e in errors)


# ── check_manifest ────────────────────────────────────────────────────────────

def test_check_manifest_missing(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    errors = check_manifest(run_dir)
    assert any("MISSING manifest" in e for e in errors)


def test_check_manifest_invalid_json(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text("not-json")
    errors = check_manifest(run_dir)
    assert any("INVALID manifest" in e for e in errors)


def test_check_manifest_no_files_key(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"other": "field"}')
    errors = check_manifest(run_dir)
    assert any("'files' or 'entries'" in e for e in errors)


def test_check_manifest_missing_category(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # manifest has files but missing "stability/" category
    manifest = {"files": [
        {"path": "contracts/POWER_CRITERIA.json", "sha256": "abc"},
        {"path": "tables/summary.json", "sha256": "def"},
        {"path": "figures/x.txt", "sha256": "ghi"},
    ]}
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    errors = check_manifest(run_dir)
    assert any("stability/" in e for e in errors)


def test_check_manifest_valid(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    errors = check_manifest(run_dir)
    assert errors == []


def test_check_manifest_hash_mismatch(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    # Tamper: change manifest hash for first file
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    errors = check_manifest(run_dir)
    assert any("hash mismatch" in e for e in errors)


# ── verify() integration ─────────────────────────────────────────────────────

def test_verify_valid_run_dir(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    result = verify(run_dir, require_stability=True)
    assert result["passed"] is True
    assert result["errors"] == []
    assert result["checks"]["contracts"] is True
    assert result["checks"]["stability"] is True
    assert result["checks"]["stability_reflects_contract"] is True
    assert result["checks"]["manifest"] is True
    assert result["checks"]["standard_outputs"] is True


def test_verify_no_stability_mode(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    # Remove stability files to simulate scan-only
    import shutil
    shutil.rmtree(run_dir / "stability")
    result = verify(run_dir, require_stability=False)
    # stability check is skipped; other checks may warn but no errors for stability
    assert result["checks"]["stability"] is True
    assert result["checks"]["stability_reflects_contract"] is True


def test_verify_missing_contracts_fails(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    (run_dir / "contracts" / "POWER_CRITERIA.json").unlink()
    result = verify(run_dir, require_stability=True)
    assert result["passed"] is False
    assert result["checks"]["contracts"] is False
