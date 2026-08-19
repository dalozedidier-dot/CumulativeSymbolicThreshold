"""Unit tests for tools/repair_ci_metrics.py."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.repair_ci_metrics import (
    HISTORY_FIELDS,
    LEGACY_HISTORY_SCHEMA_A,
    LEGACY_RUNS_SCHEMA_A,
    RUNS_INDEX_FIELDS,
    is_header_row,
    looks_like_legacy_runs_row,
    main,
    remap_row,
)

SHA64_A = "b" * 64
SHA64_B = "c" * 64
COMMIT = "0494e2fef017398b0476dfcc6c32f4e82e4424a7"
TS = "2026-07-02T17:49:42.520023+00:00"

# A row written under LEGACY_RUNS_SCHEMA_A: commit_sha sits in the slot the
# canonical schema reserves for run_mode, and run_mode lands in manifest_sha256.
LEGACY_RUNS_ROW = [
    "28610294797", "20260702_174847", "brisbane_stateprob", "qcc",
    COMMIT, "high", "True", "full", SHA64_A, SHA64_B, TS,
]
CANONICAL_RUNS_ROW = [
    "28610294797", "20260702_174847", "brisbane_stateprob", "qcc",
    "full", "high", "True", SHA64_A, SHA64_B, COMMIT, "QCC StateProb",
]


# ── looks_like_legacy_runs_row ────────────────────────────────────────────────

def test_detects_legacy_runs_row():
    assert looks_like_legacy_runs_row(LEGACY_RUNS_ROW) is True


def test_canonical_row_is_not_flagged_as_legacy():
    assert looks_like_legacy_runs_row(CANONICAL_RUNS_ROW) is False


def test_wrong_length_row_is_not_legacy():
    assert looks_like_legacy_runs_row(["a", "b", "c"]) is False


def test_legacy_and_canonical_schemas_have_equal_width():
    # The reason content-based detection is needed at all: length cannot
    # discriminate these two layouts.
    assert len(LEGACY_RUNS_SCHEMA_A) == len(RUNS_INDEX_FIELDS)


# ── remap_row ─────────────────────────────────────────────────────────────────

def test_remap_legacy_runs_row_restores_canonical_columns():
    m = remap_row(LEGACY_RUNS_ROW, LEGACY_RUNS_SCHEMA_A, RUNS_INDEX_FIELDS)
    assert m["run_mode"] == "full"
    assert m["commit_sha"] == COMMIT
    assert m["manifest_sha256"] == SHA64_A
    assert m["stability_criteria_sha256"] == SHA64_B


def test_remap_aliases_legacy_workflow_column_to_workflow_source():
    row = [TS, "1", "20260101_000000", "ds", "qcc", COMMIT, "high", "True",
           SHA64_B, "full", "QCC StateProb — Full Diagnostic"]
    m = remap_row(row, LEGACY_HISTORY_SCHEMA_A, HISTORY_FIELDS)
    assert m["workflow_source"] == "QCC StateProb — Full Diagnostic"
    assert m["run_mode"] == "full"
    assert m["commit_sha"] == COMMIT


# ── is_header_row ─────────────────────────────────────────────────────────────

def test_is_header_row_detects_canonical_headers():
    assert is_header_row(RUNS_INDEX_FIELDS) is True
    assert is_header_row(HISTORY_FIELDS) is True


def test_is_header_row_rejects_data_row():
    assert is_header_row(CANONICAL_RUNS_ROW) is False


# ── Integration: main() ───────────────────────────────────────────────────────

def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_main_repairs_column_shifted_files(tmp_path, monkeypatch):
    d = tmp_path / "ci_metrics"
    d.mkdir()
    # Both files carry the canonical *header* but legacy-ordered *rows* — the
    # corruption produced by appending without rewriting the header.
    _write(d / "runs_index.csv", RUNS_INDEX_FIELDS, [LEGACY_RUNS_ROW])
    _write(
        d / "history.csv",
        RUNS_INDEX_FIELDS,
        [[TS, "28610294797", "20260702_174847", "brisbane_stateprob", "qcc",
          COMMIT, "high", "True", SHA64_B, "full", "QCC StateProb"]],
    )

    monkeypatch.setattr("sys.argv", ["repair_ci_metrics", "--ci-metrics-dir", str(d)])
    main()

    with open(d / "runs_index_repaired.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["run_mode"] == "full"
    assert rows[0]["commit_sha"] == COMMIT
    assert rows[0]["manifest_sha256"] == SHA64_A

    with open(d / "history_repaired.csv", encoding="utf-8") as f:
        hrows = list(csv.DictReader(f))
    assert hrows[0]["run_mode"] == "full"
    assert hrows[0]["workflow_source"] == "QCC StateProb"

    report = json.loads((d / "repair_report.json").read_text(encoding="utf-8"))
    assert report["runs_index"]["remapped_legacy"] == 1
    assert report["runs_index"]["skipped"] == 0
    assert report["history"]["skipped"] == 0


def test_main_leaves_already_canonical_rows_untouched(tmp_path, monkeypatch):
    d = tmp_path / "ci_metrics"
    d.mkdir()
    _write(d / "runs_index.csv", RUNS_INDEX_FIELDS, [CANONICAL_RUNS_ROW])
    _write(d / "history.csv", HISTORY_FIELDS, [[TS, *CANONICAL_RUNS_ROW]])

    monkeypatch.setattr("sys.argv", ["repair_ci_metrics", "--ci-metrics-dir", str(d)])
    main()

    with open(d / "runs_index_repaired.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [rows[0][k] for k in RUNS_INDEX_FIELDS] == CANONICAL_RUNS_ROW

    report = json.loads((d / "repair_report.json").read_text(encoding="utf-8"))
    assert report["runs_index"]["remapped_legacy"] == 0
