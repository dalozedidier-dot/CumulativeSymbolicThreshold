"""Unit tests for tools/collect_ci_metrics.py."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from tools.collect_ci_metrics import (
    HISTORY_FIELDS,
    RUNS_INDEX_FIELDS,
    _get_commit_sha,
    _get_dataset_id,
    _get_evidence_strength,
    _infer_run_mode,
    _infer_sector,
    main,
)


# ── _infer_sector ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dataset_id,run_mode,expected", [
    ("qcc_canonical_full", "full", "qcc"),
    ("brisbane_stateprob", "scan_only", "qcc"),
    ("co2_mauna_loa", "full", "climate"),
    ("gistemp_v4", "full", "climate"),
    ("sp500_daily", "full", "finance"),
    ("btc_price", "scan_only", "finance"),
    ("mlperf_inference", "scan_only", "ai_tech"),
    ("twitter_sentiment", "full", "social"),
    ("google_trends_anxiety", "full", "psych"),
    ("ecdc_flu_weekly", "full", "bio"),
    ("unknown_dataset", "canonical", "real_data"),
    ("unknown_dataset", "real_run", "real_data"),
    ("unknown_dataset", "scan_only", "unknown"),
])
def test_infer_sector(dataset_id, run_mode, expected):
    assert _infer_sector(dataset_id, run_mode) == expected


# ── _infer_run_mode ───────────────────────────────────────────────────────────

def test_infer_run_mode_explicit():
    assert _infer_run_mode({"run_mode": "full"}, has_stability=False) == "full"
    assert _infer_run_mode({"mode": "scan_only"}, has_stability=True) == "scan_only"


def test_infer_run_mode_fallback_stability():
    assert _infer_run_mode({}, has_stability=True) == "full"
    assert _infer_run_mode({}, has_stability=False) == "scan_only"


def test_infer_run_mode_strips_whitespace():
    assert _infer_run_mode({"run_mode": "  full  "}, has_stability=False) == "full"


# ── _get_evidence_strength ────────────────────────────────────────────────────

def test_get_evidence_strength_direct():
    assert _get_evidence_strength({"evidence_strength": "high"}) == "high"


def test_get_evidence_strength_nested():
    summary = {"power_diagnostic": {"evidence_strength": "medium"}}
    assert _get_evidence_strength(summary) == "medium"


def test_get_evidence_strength_nested_evidence_key():
    summary = {"power_diagnostic": {"evidence": "low"}}
    assert _get_evidence_strength(summary) == "low"


def test_get_evidence_strength_missing():
    assert _get_evidence_strength({}) == ""


# ── _get_commit_sha ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("field", ["commit_sha", "head_sha", "sha", "git_sha"])
def test_get_commit_sha_field_names(field):
    sha = "abc123def456"
    assert _get_commit_sha({field: sha}) == sha


def test_get_commit_sha_missing():
    assert _get_commit_sha({}) == ""


def test_get_commit_sha_priority():
    # commit_sha is checked first
    summary = {"commit_sha": "first", "sha": "second"}
    assert _get_commit_sha(summary) == "first"


# ── _get_dataset_id ───────────────────────────────────────────────────────────

def test_get_dataset_id_plain():
    assert _get_dataset_id({"dataset_id": "my_dataset"}) == "my_dataset"


def test_get_dataset_id_path():
    assert _get_dataset_id({"input_csv": "/data/climate/co2_mm_mlo.csv"}) == "co2_mm_mlo"



def test_get_dataset_id_missing():
    assert _get_dataset_id({}) == ""


# ── Integration: main() ───────────────────────────────────────────────────────

def _make_artifact_tree(base: Path, github_run_id: str = "12345") -> Path:
    """Create a minimal _collected_artifacts tree for testing main()."""
    run_dir = base / f"run_{github_run_id}" / "some_job" / "runs" / "20260101_120000"
    (run_dir / "tables").mkdir(parents=True)
    (run_dir / "stability").mkdir(parents=True)

    summary = {
        "dataset_id": "qcc_test_artifact",
        "sector": "qcc",
        "run_mode": "full",
        "evidence_strength": "high",
        "commit_sha": "deadbeef1234",
        "workflow_source": "QCC Canonical Full",
    }
    (run_dir / "tables" / "summary.json").write_text(json.dumps(summary))

    stability = {
        "criteria_sha256": "aabbcc",
        "stability_check": {"all_pass": True},
    }
    (run_dir / "stability" / "stability_summary.json").write_text(json.dumps(stability))

    manifest = {"manifest_sha256": "deadcafe"}
    (run_dir / "manifest.json").write_text(json.dumps(manifest))

    return base


def test_main_creates_csvs(tmp_path, monkeypatch):
    in_dir = tmp_path / "artifacts"
    _make_artifact_tree(in_dir)
    out_dir = tmp_path / "metrics"

    monkeypatch.setattr(
        "sys.argv", ["collect_ci_metrics", "--in-dir", str(in_dir), "--out-dir", str(out_dir)]
    )
    main()

    runs_index = out_dir / "runs_index.csv"
    history = out_dir / "history.csv"
    assert runs_index.exists()
    assert history.exists()


def test_main_correct_schema_headers(tmp_path, monkeypatch):
    in_dir = tmp_path / "artifacts"
    _make_artifact_tree(in_dir)
    out_dir = tmp_path / "metrics"

    monkeypatch.setattr(
        "sys.argv", ["collect_ci_metrics", "--in-dir", str(in_dir), "--out-dir", str(out_dir)]
    )
    main()

    with open(out_dir / "runs_index.csv") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == RUNS_INDEX_FIELDS

    with open(out_dir / "history.csv") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == HISTORY_FIELDS


def test_main_workflow_source_captured(tmp_path, monkeypatch):
    in_dir = tmp_path / "artifacts"
    _make_artifact_tree(in_dir, github_run_id="99999")
    out_dir = tmp_path / "metrics"

    monkeypatch.setattr(
        "sys.argv", ["collect_ci_metrics", "--in-dir", str(in_dir), "--out-dir", str(out_dir)]
    )
    main()

    with open(out_dir / "runs_index.csv") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["workflow_source"] == "QCC Canonical Full"
    assert rows[0]["github_run_id"] == "99999"
    assert rows[0]["dataset_id"] == "qcc_test_artifact"


def test_main_run_meta_overrides_workflow_source(tmp_path, monkeypatch):
    in_dir = tmp_path / "artifacts"
    base = _make_artifact_tree(in_dir, github_run_id="77777")
    # run_meta_path in code = dirname(tables)/../../../run_meta.json
    # = runs/<ts>/tables → ../../.. → some_job/run_meta.json
    run_meta_dir = base / "run_77777" / "some_job"
    (run_meta_dir / "run_meta.json").write_text(
        json.dumps({"workflowName": "From run_meta"})
    )
    out_dir = tmp_path / "metrics"

    monkeypatch.setattr(
        "sys.argv", ["collect_ci_metrics", "--in-dir", str(in_dir), "--out-dir", str(out_dir)]
    )
    main()

    with open(out_dir / "runs_index.csv") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["workflow_source"] == "From run_meta"


def test_main_append_deduplicates(tmp_path, monkeypatch):
    in_dir = tmp_path / "artifacts"
    _make_artifact_tree(in_dir, github_run_id="55555")
    out_dir = tmp_path / "metrics"

    argv_base = ["collect_ci_metrics", "--in-dir", str(in_dir), "--out-dir", str(out_dir)]

    monkeypatch.setattr("sys.argv", argv_base)
    main()

    monkeypatch.setattr("sys.argv", argv_base + ["--append"])
    main()

    with open(out_dir / "runs_index.csv") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1, "Duplicate row should not be appended"


def test_main_no_runs_creates_empty_csvs(tmp_path, monkeypatch):
    in_dir = tmp_path / "empty_artifacts"
    in_dir.mkdir()
    out_dir = tmp_path / "metrics"

    monkeypatch.setattr(
        "sys.argv", ["collect_ci_metrics", "--in-dir", str(in_dir), "--out-dir", str(out_dir)]
    )
    main()

    assert (out_dir / "runs_index.csv").exists()
    assert (out_dir / "history.csv").exists()

    with open(out_dir / "runs_index.csv") as f:
        rows = list(csv.DictReader(f))
    assert rows == []
