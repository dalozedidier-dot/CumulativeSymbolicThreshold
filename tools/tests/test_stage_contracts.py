"""Unit tests for tools/stage_contracts.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.stage_contracts import stage_contracts, _find_latest_run_dir


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_contracts(tmp_path: Path) -> tuple[Path, Path]:
    power = tmp_path / "POWER_CRITERIA.json"
    stability = tmp_path / "STABILITY_CRITERIA.json"
    power.write_text(json.dumps({"schema": "qcc.power_criteria.v1"}))
    stability.write_text(json.dumps({"max_relative_variation": 0.3}))
    return power, stability


def _make_run_dir(tmp_path: Path, name: str = "20260101_000000") -> Path:
    run_dir = tmp_path / "runs" / name
    run_dir.mkdir(parents=True)
    return run_dir


# ── stage_contracts() ─────────────────────────────────────────────────────────


def test_stage_contracts_required_only(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)

    result = stage_contracts(run_dir, power_criteria=power, stability_criteria=stability)

    assert result["errors"] == []
    contracts_dir = run_dir / "contracts"
    assert (contracts_dir / "POWER_CRITERIA.json").exists()
    assert (contracts_dir / "STABILITY_CRITERIA.json").exists()


def test_stage_contracts_hashes_written(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)

    result = stage_contracts(run_dir, power_criteria=power, stability_criteria=stability)

    assert "POWER_CRITERIA.json" in result["staged"]
    assert len(result["staged"]["POWER_CRITERIA.json"]["sha256"]) == 64
    assert len(result["staged"]["STABILITY_CRITERIA.json"]["sha256"]) == 64


def test_stage_contracts_with_mapping(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"type": "cross"}))

    result = stage_contracts(
        run_dir, power_criteria=power, stability_criteria=stability, mapping=mapping
    )

    assert (run_dir / "contracts" / "mapping_cross_conditions.json").exists()
    assert "mapping_cross_conditions.json" in result["staged"]


def test_stage_contracts_with_inventory(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)
    inv = tmp_path / "inventory.csv"
    inv.write_text("path,sha256\nfile.csv,abc\n")

    result = stage_contracts(
        run_dir, power_criteria=power, stability_criteria=stability, input_inventory=inv
    )

    assert (run_dir / "contracts" / "input_inventory.csv").exists()


def test_stage_contracts_missing_power_fails(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    _, stability = _make_contracts(tmp_path)
    missing = tmp_path / "nonexistent.json"

    with pytest.raises(SystemExit):
        stage_contracts(run_dir, power_criteria=missing, stability_criteria=stability)


def test_stage_contracts_missing_stability_fails(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, _ = _make_contracts(tmp_path)
    missing = tmp_path / "nonexistent.json"

    with pytest.raises(SystemExit):
        stage_contracts(run_dir, power_criteria=power, stability_criteria=missing)


def test_stage_contracts_no_fail_fast(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    missing = tmp_path / "nonexistent.json"

    result = stage_contracts(
        run_dir,
        power_criteria=missing,
        stability_criteria=missing,
        fail_fast=False,
    )
    assert len(result["errors"]) == 2


def test_stage_contracts_extra_files(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)
    extra = tmp_path / "extra_notes.txt"
    extra.write_text("notes")

    result = stage_contracts(
        run_dir, power_criteria=power, stability_criteria=stability, extra_files=[extra]
    )

    assert (run_dir / "contracts" / "extra_notes.txt").exists()
    assert "extra_notes.txt" in result["staged"]


def test_stage_contracts_optional_missing_files_skipped(tmp_path):
    """If optional files don't exist, staging succeeds without error."""
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)
    nonexistent = tmp_path / "no_such_file.csv"

    result = stage_contracts(
        run_dir,
        power_criteria=power,
        stability_criteria=stability,
        input_inventory=nonexistent,
    )
    assert result["errors"] == []
    assert "input_inventory.csv" not in result["staged"]


def test_stage_contracts_contracts_dir_created(tmp_path):
    run_dir = _make_run_dir(tmp_path)
    power, stability = _make_contracts(tmp_path)

    stage_contracts(run_dir, power_criteria=power, stability_criteria=stability)

    assert (run_dir / "contracts").is_dir()


# ── _find_latest_run_dir ─────────────────────────────────────────────────────


def test_find_latest_run_dir_picks_most_recent(tmp_path):
    out_root = tmp_path / "out"
    (out_root / "runs" / "20260101_000000").mkdir(parents=True)
    (out_root / "runs" / "20260202_000000").mkdir(parents=True)
    latest = _find_latest_run_dir(out_root)
    assert latest.name == "20260202_000000"


def test_find_latest_run_dir_no_runs_raises(tmp_path):
    out_root = tmp_path / "out"
    (out_root / "runs").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        _find_latest_run_dir(out_root)


def test_find_latest_run_dir_no_runs_dir_raises(tmp_path):
    out_root = tmp_path / "out"
    out_root.mkdir()
    with pytest.raises(FileNotFoundError):
        _find_latest_run_dir(out_root)
