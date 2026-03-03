#!/usr/bin/env python3
"""
collect_ci_metrics.py (v2)
Append-only collector that is robust to schema drift across summary.json files.

Fixes:
- sector/run_mode inference from dataset_id when missing.
- run_mode inference from presence of stability outputs.
- supports both old and new field names in summary.json / stability_summary.json / manifest.json.
- FAIL-SOFT: ensures CSVs exist even if no runs found.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

RUNS_INDEX_FIELDS = [
    "github_run_id",
    "run_dir_name",
    "dataset_id",
    "sector",
    "commit_sha",
    "evidence_strength",
    "all_pass",
    "run_mode",
    "manifest_sha256",
    "stability_criteria_sha256",
]

HISTORY_FIELDS = ["timestamp"] + RUNS_INDEX_FIELDS + ["workflow"]


def _read_json(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ensure_csv(path: str, fields: List[str]) -> None:
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()


def _find_summary_paths(in_dir: str) -> List[str]:
    # Find any */runs/<ts>/tables/summary.json
    hits = []
    for root, _, files in os.walk(in_dir):
        if "summary.json" in files and os.path.basename(root) == "tables":
            run_dir = os.path.dirname(root)  # .../runs/<ts>
            if os.path.basename(os.path.dirname(run_dir)) == "runs":
                hits.append(os.path.join(root, "summary.json"))
    return sorted(set(hits))


def _infer_github_run_id(path: str) -> str:
    # path contains .../_collected_artifacts/run_<id>/...
    parts = path.split(os.sep)
    for p in parts:
        if p.startswith("run_") and p[4:].isdigit():
            return p[4:]
    return ""


def _infer_run_dir_name(summary_path: str) -> str:
    # .../runs/<ts>/tables/summary.json -> <ts>
    return os.path.basename(os.path.dirname(os.path.dirname(summary_path)))


def _infer_sector(dataset_id: str, run_mode: str) -> str:
    s = (dataset_id or "").lower()
    m = (run_mode or "").lower()
    if s.startswith("qcc") or "stateprob" in s or "brisbane" in s:
        return "qcc"
    if "climate" in s or "co2" in s or "gistemp" in s:
        return "climate"
    if "finance" in s or "sp500" in s or "btc" in s:
        return "finance"
    if "ai" in s or "llm" in s or "mlperf" in s:
        return "ai_tech"
    if "twitter" in s or "social" in s:
        return "social"
    if "google_trends" in s or "psych" in s or "wvs" in s:
        return "psych"
    if "ecdc" in s or "epidemic" in s or "bio" in s:
        return "bio"
    if "real" in m or "canonical" in m:
        return "real_data"
    return "unknown"


def _infer_run_mode(summary: Dict, has_stability: bool) -> str:
    for k in ("run_mode", "mode"):
        v = summary.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # If no explicit run_mode:
    return "full" if has_stability else "scan_only"


def _get_evidence_strength(summary: Dict) -> str:
    v = summary.get("evidence_strength")
    if isinstance(v, str) and v:
        return v
    pd = summary.get("power_diagnostic")
    if isinstance(pd, dict):
        v2 = pd.get("evidence_strength") or pd.get("evidence")
        if isinstance(v2, str) and v2:
            return v2
    return ""


def _get_commit_sha(summary: Dict) -> str:
    for k in ("commit_sha", "head_sha", "sha", "git_sha"):
        v = summary.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _get_dataset_id(summary: Dict) -> str:
    for k in ("dataset_id", "dataset", "input_csv", "dataset_path"):
        v = summary.get(k)
        if isinstance(v, str) and v:
            # If input_csv is a path, take basename stem.
            if "/" in v or "\\" in v:
                base = os.path.basename(v)
                return os.path.splitext(base)[0]
            return v
    return ""


def _load_existing_keys(path: str) -> set:
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            # unique key = github_run_id + run_dir_name
            keys.add((row.get("github_run_id",""), row.get("run_dir_name","")))
    return keys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    runs_index_path = os.path.join(args.out_dir, "runs_index.csv")
    history_path = os.path.join(args.out_dir, "history.csv")

    _ensure_csv(runs_index_path, RUNS_INDEX_FIELDS)
    _ensure_csv(history_path, HISTORY_FIELDS)

    summaries = _find_summary_paths(args.in_dir)
    if not summaries:
        print(f"[INFO] No runs found under {args.in_dir}.")
        return

    existing = _load_existing_keys(runs_index_path) if args.append else set()
    ts = datetime.utcnow().isoformat() + "Z"

    rows_index = []
    rows_hist = []

    for sp in summaries:
        summary = _read_json(sp) or {}
        run_dir = os.path.dirname(os.path.dirname(sp))  # .../runs/<ts>
        has_stability = os.path.exists(os.path.join(run_dir, "stability", "stability_summary.json"))
        stability = _read_json(os.path.join(run_dir, "stability", "stability_summary.json")) or {}
        manifest = _read_json(os.path.join(run_dir, "manifest.json")) or {}

        github_run_id = _infer_github_run_id(sp)
        run_dir_name = _infer_run_dir_name(sp)
        key = (github_run_id, run_dir_name)
        if args.append and key in existing:
            continue

        dataset_id = _get_dataset_id(summary)
        run_mode = _infer_run_mode(summary, has_stability)
        sector = summary.get("sector") or summary.get("domain") or ""
        if not sector:
            sector = _infer_sector(dataset_id, run_mode)

        evidence_strength = _get_evidence_strength(summary)
        # all_pass: from stability if exists, else from summary if scan-only records it
        all_pass = ""
        if isinstance(stability.get("stability_check"), dict):
            apass = stability["stability_check"].get("all_pass")
            if apass is not None:
                all_pass = bool(apass)
        if all_pass == "" and "all_pass" in summary:
            all_pass = summary.get("all_pass")

        stability_criteria_sha256 = stability.get("criteria_sha256", "")
        manifest_sha256 = manifest.get("manifest_sha256") or manifest.get("sha256") or ""

        commit_sha = _get_commit_sha(summary)

        row = {
            "github_run_id": github_run_id,
            "run_dir_name": run_dir_name,
            "dataset_id": dataset_id,
            "sector": sector,
            "commit_sha": commit_sha,
            "evidence_strength": evidence_strength,
            "all_pass": all_pass,
            "run_mode": run_mode,
            "manifest_sha256": manifest_sha256,
            "stability_criteria_sha256": stability_criteria_sha256,
        }
        rows_index.append(row)
        rows_hist.append({"timestamp": ts, **row, "workflow": ""})

    if rows_index:
        with open(runs_index_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=RUNS_INDEX_FIELDS)
            for r in rows_index:
                w.writerow({k: r.get(k, "") for k in RUNS_INDEX_FIELDS})

        with open(history_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
            for r in rows_hist:
                w.writerow({k: r.get(k, "") for k in HISTORY_FIELDS})

    print(f"[INFO] Appended {len(rows_index)} rows.")


if __name__ == "__main__":
    main()
