#!/usr/bin/env python3
"""
Append-only CI metrics collector.

Scans downloaded artifacts for summary files and extracts:
- dataset_id, sector, run_mode
- evidence_strength, stability all_pass
- manifest sha256, stability criteria sha256
- github_run_id (inferred from path run_<id>)
- commit_sha (optional, from run_meta.json if present)

Supported layouts:
A) QCC/QCC-like:
  .../runs/<ts>/tables/summary.json
  .../runs/<ts>/stability/stability_summary.json (optional)
  .../runs/<ts>/manifest.json (optional)

B) ORI-C real-data smoke:
  .../<some_run_root>/tables/summary.json
  .../<some_run_root>/manifest.json (optional)
  .../<some_run_root>/stability/stability_summary.json (optional)

FAIL-SOFT:
- If nothing found, ensures CSV headers exist and exits 0.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


FIELDS = [
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
    "timestamp",
]


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ensure_csv(path: str, fieldnames: List[str]) -> None:
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fieldnames).writeheader()


def _existing_keys(path: str) -> set:
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            k = (row.get("github_run_id",""), row.get("run_dir_name",""))
            if any(k):
                keys.add(k)
    return keys


def _append_rows(path: str, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    _ensure_csv(path, fieldnames)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _infer_github_run_id(path: str) -> str:
    # look for /run_<id>/
    parts = path.split(os.sep)
    for p in parts:
        if p.startswith("run_") and p[4:].isdigit():
            return p[4:]
    return ""


def _run_dir_name(run_root: str) -> str:
    return os.path.basename(run_root.rstrip(os.sep))


def _infer_dataset_id(summary: Dict[str, Any]) -> str:
    if isinstance(summary.get("dataset_id"), str) and summary["dataset_id"].strip():
        return summary["dataset_id"].strip()
    # ORI-C real-data smoke uses input_csv
    ic = summary.get("input_csv")
    if isinstance(ic, str) and ic.strip():
        base = os.path.basename(ic.strip())
        return os.path.splitext(base)[0]
    return "unknown"


def _infer_run_mode(summary: Dict[str, Any], dataset_id: str) -> str:
    for k in ("run_mode", "mode"):
        v = summary.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # fallbacks
    if dataset_id.startswith("qcc_"):
        return "full"
    if "real_data" in dataset_id or isinstance(summary.get("input_csv"), str):
        return "real_data"
    return ""


def _infer_sector(summary: Dict[str, Any], dataset_id: str, run_mode: str) -> str:
    v = summary.get("sector")
    if isinstance(v, str) and v.strip():
        return v.strip()
    # infer from run_mode / dataset_id
    did = (dataset_id or "").lower()
    rm = (run_mode or "").lower()
    if "qcc" in did or did.startswith("stateprob") or did.startswith("qcc_"):
        return "qcc"
    if "real_data" in rm or isinstance(summary.get("input_csv"), str):
        return "real_data"
    # sector smoke packs (non-qcc)
    for s in ("finance", "climate", "psych", "social", "ai_tech", "bio"):
        if s in did or s in rm:
            return s
    return "unknown"


def _extract_evidence(summary: Dict[str, Any]) -> str:
    v = summary.get("evidence_strength")
    if isinstance(v, str) and v.strip():
        return v.strip()
    pd = summary.get("power_diagnostic")
    if isinstance(pd, dict):
        v2 = pd.get("evidence_strength")
        if isinstance(v2, str) and v2.strip():
            return v2.strip()
    return ""


def _extract_all_pass(stability: Dict[str, Any]) -> str:
    sc = stability.get("stability_check")
    if isinstance(sc, dict) and "all_pass" in sc:
        return str(sc["all_pass"])
    if "all_pass" in stability:
        return str(stability["all_pass"])
    return ""


def _find_run_roots(in_dir: str) -> List[str]:
    # Find any tables/summary.json, treat its parent as run_root
    run_roots = set()
    for root, _, files in os.walk(in_dir):
        if os.path.basename(root) != "tables":
            continue
        if "summary.json" not in files:
            continue
        run_root = os.path.dirname(root)
        run_roots.add(run_root)
    return sorted(run_roots)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir
    runs_index = os.path.join(out_dir, "runs_index.csv")
    history = os.path.join(out_dir, "history.csv")

    _ensure_csv(runs_index, FIELDS)
    _ensure_csv(history, FIELDS)

    roots = _find_run_roots(args.in_dir)
    if not roots:
        print(f"[INFO] No tables/summary.json found under {args.in_dir}.")
        return

    existing = _existing_keys(runs_index) if args.append else set()
    ts = datetime.now(timezone.utc).isoformat()

    rows: List[Dict[str, Any]] = []
    for run_root in roots:
        gid = _infer_github_run_id(run_root)
        rname = _run_dir_name(run_root)
        key = (gid, rname)
        if args.append and key in existing:
            continue

        summary = _read_json(os.path.join(run_root, "tables", "summary.json")) or {}
        stability = _read_json(os.path.join(run_root, "stability", "stability_summary.json")) or {}
        manifest = _read_json(os.path.join(run_root, "manifest.json")) or {}
        run_meta = _read_json(os.path.join(run_root, "run_meta.json")) or _read_json(os.path.join(os.path.dirname(run_root), "run_meta.json")) or {}

        dataset_id = _infer_dataset_id(summary)
        run_mode = _infer_run_mode(summary, dataset_id)
        sector = _infer_sector(summary, dataset_id, run_mode)

        row = {
            "github_run_id": gid,
            "run_dir_name": rname,
            "dataset_id": dataset_id,
            "sector": sector,
            "commit_sha": run_meta.get("headSha","") or run_meta.get("commit_sha","") or "",
            "evidence_strength": _extract_evidence(summary),
            "all_pass": _extract_all_pass(stability),
            "run_mode": run_mode,
            "manifest_sha256": manifest.get("manifest_sha256","") or manifest.get("sha256","") or "",
            "stability_criteria_sha256": stability.get("criteria_sha256","") or "",
            "timestamp": ts,
        }
        rows.append(row)

    _append_rows(runs_index, FIELDS, rows)
    _append_rows(history, FIELDS, rows)
    print(f"[INFO] Appended {len(rows)} rows.")

if __name__ == "__main__":
    main()
