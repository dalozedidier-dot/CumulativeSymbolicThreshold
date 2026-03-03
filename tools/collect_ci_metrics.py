#!/usr/bin/env python3
"""
Collect metrics from downloaded artifacts and append to ci_metrics CSVs.

Input layout (expected):
  <in-dir>/
    run_<runid>/... (downloaded via `gh run download`)
      (one or more artifacts unpacked)
      .../runs/<timestamp>/tables/summary.json
      .../runs/<timestamp>/stability/stability_summary.json (optional)
      .../runs/<timestamp>/manifest.json

This tool:
- scans recursively for runs/<ts>/tables/summary.json
- for each run_dir, reads:
    - summary.json (required)
    - manifest.json (optional but recommended)
    - stability_summary.json (optional)
- writes/append-only:
    - <out-dir>/runs_index.csv
    - <out-dir>/history.csv  (one row per run, same schema; kept for compatibility)

It is FAIL-SOFT:
- if no runs found, ensures CSV files exist with headers and exits 0.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


RUNS_INDEX_FIELDS = [
    "run_dir",
    "run_id",
    "sector",
    "dataset_id",
    "run_mode",
    "evidence_strength",
    "stability_all_pass",
    "stability_criteria_sha256",
    "manifest_sha256",
]

HISTORY_FIELDS = ["ts_utc"] + RUNS_INDEX_FIELDS


def _safe_get(d: Dict, path: List[str], default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _read_json(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _find_run_dirs(in_dir: str) -> List[str]:
    # We look for .../runs/<ts>/tables/summary.json
    matches: List[str] = []
    for root, _, files in os.walk(in_dir):
        if "summary.json" not in files:
            continue
        if os.path.basename(root) != "tables":
            continue
        # root = .../runs/<ts>/tables
        run_dir = os.path.dirname(root)  # .../runs/<ts>
        if os.path.basename(os.path.dirname(run_dir)) != "runs":
            # ensure path segment
            continue
        matches.append(run_dir)
    return sorted(set(matches))


def _infer_run_id_from_path(run_dir: str) -> str:
    # Best-effort: if the path includes /run_<id>/, use that.
    parts = run_dir.split(os.sep)
    for p in parts:
        if p.startswith("run_") and p[4:].isdigit():
            return p[4:]
    return ""


def _ensure_csv(path: str, fieldnames: List[str]) -> None:
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()


def _load_existing_keys(path: str) -> set:
    # key is run_dir
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("run_dir"):
                keys.add(row["run_dir"])
    return keys


def _append_rows(path: str, fieldnames: List[str], rows: List[Dict]) -> None:
    if not rows:
        return
    _ensure_csv(path, fieldnames)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        for row in rows:
            # only keep known fields
            cleaned = {k: row.get(k, "") for k in fieldnames}
            w.writerow(cleaned)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--append", action="store_true", help="Append-only; skip existing run_dir rows.")
    args = ap.parse_args()

    in_dir = args.in_dir
    out_dir = args.out_dir

    runs_index_path = os.path.join(out_dir, "runs_index.csv")
    history_path = os.path.join(out_dir, "history.csv")

    _ensure_csv(runs_index_path, RUNS_INDEX_FIELDS)
    _ensure_csv(history_path, HISTORY_FIELDS)

    run_dirs = _find_run_dirs(in_dir)
    if not run_dirs:
        print(f"[INFO] No run dirs found under {in_dir}. CSVs ensured, nothing to append.")
        return

    existing = _load_existing_keys(runs_index_path) if args.append else set()

    rows_index: List[Dict] = []
    rows_history: List[Dict] = []

    ts_utc = __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    for run_dir in run_dirs:
        if args.append and run_dir in existing:
            continue

        summary = _read_json(os.path.join(run_dir, "tables", "summary.json")) or {}
        stability = _read_json(os.path.join(run_dir, "stability", "stability_summary.json")) or {}
        manifest = _read_json(os.path.join(run_dir, "manifest.json")) or {}

        sector = summary.get("sector", "")
        dataset_id = summary.get("dataset_id", "")
        run_mode = summary.get("run_mode", summary.get("mode", ""))
        evidence_strength = summary.get("evidence_strength", _safe_get(summary, ["power_diagnostic", "evidence_strength"], ""))
        stability_all_pass = _safe_get(stability, ["stability_check", "all_pass"], "")
        # Criteria sha may be in stability_summary; prefer explicit
        stability_criteria_sha256 = stability.get("criteria_sha256", "")
        manifest_sha256 = manifest.get("manifest_sha256", "") or manifest.get("sha256", "")

        row = {
            "run_dir": run_dir,
            "run_id": _infer_run_id_from_path(run_dir),
            "sector": sector,
            "dataset_id": dataset_id,
            "run_mode": run_mode,
            "evidence_strength": evidence_strength,
            "stability_all_pass": str(stability_all_pass),
            "stability_criteria_sha256": stability_criteria_sha256,
            "manifest_sha256": manifest_sha256,
        }
        rows_index.append(row)
        rows_history.append({"ts_utc": ts_utc, **row})

    _append_rows(runs_index_path, RUNS_INDEX_FIELDS, rows_index)
    _append_rows(history_path, HISTORY_FIELDS, rows_history)

    print(f"[INFO] Appended {len(rows_index)} runs into {runs_index_path} and {history_path}.")


if __name__ == "__main__":
    main()
