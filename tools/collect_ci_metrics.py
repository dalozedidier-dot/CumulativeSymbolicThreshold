#!/usr/bin/env python3
"""
collect_ci_metrics.py (v3 strict)

Goals:
- Single canonical schema for runs_index.csv and history.csv.
- Append-only without re-writing headers.
- Refuse to write if header mismatch is detected (prevents silent column drift).

This script assumes inputs contain run dirs with tables/summary.json, manifest.json,
and optionally stability/stability_summary.json, under any _collected_artifacts/run_<id>/... layout.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RUNS_INDEX_FIELDS = [
    "github_run_id",
    "run_dir_name",
    "dataset_id",
    "sector",
    "run_mode",
    "evidence_strength",
    "all_pass",
    "manifest_sha256",
    "stability_criteria_sha256",
    "commit_sha",
    "workflow_source",
]

HISTORY_FIELDS = ["timestamp"] + RUNS_INDEX_FIELDS

def _read_json(p: Path) -> Optional[Dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _first_line(p: Path) -> str:
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            return f.readline().strip()
    except FileNotFoundError:
        return ""

def _expected_header(fields: List[str]) -> str:
    return ",".join(fields)

def _ensure_csv_with_header(p: Path, fields: List[str]) -> None:
    _ensure_dir(p)
    if not p.exists():
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
        return
    # If exists, enforce header matches exactly.
    got = _first_line(p)
    exp = _expected_header(fields)
    if got != exp:
        raise SystemExit(f"Header mismatch in {p}: got={got!r} expected={exp!r}. Refusing to append.")

def _infer_github_run_id(path: Path) -> str:
    parts = path.parts
    for part in parts:
        if part.startswith("run_") and part[4:].isdigit():
            return part[4:]
    return ""

def _infer_run_dir_name(summary_path: Path) -> str:
    # .../runs/<ts>/tables/summary.json
    return summary_path.parents[1].name

def _get_str(d: Dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _dataset_id(summary: Dict) -> str:
    v = _get_str(summary, "dataset_id", "dataset", "dataset_name")
    if v:
        return v
    # real-data often has input_csv
    in_csv = _get_str(summary, "input_csv", "dataset_path")
    if in_csv:
        base = os.path.basename(in_csv)
        return os.path.splitext(base)[0]
    return ""

def _run_mode(summary: Dict, has_stability: bool) -> str:
    v = _get_str(summary, "run_mode", "mode")
    if v:
        return v
    return "full" if has_stability else "scan_only"

def _sector(summary: Dict, dataset_id: str, run_mode: str) -> str:
    v = _get_str(summary, "sector", "domain")
    if v:
        return v
    s = (dataset_id or "").lower()
    m = (run_mode or "").lower()
    if s.startswith("qcc") or "stateprob" in s or "brisbane" in s or "polaron" in s:
        return "qcc"
    if "co2" in s or "gistemp" in s or "climate" in s:
        return "climate"
    if "sp500" in s or "btc" in s or "finance" in s:
        return "finance"
    if "llm" in s or "mlperf" in s or "ai" in s:
        return "ai_tech"
    if "twitter" in s or "social" in s:
        return "social"
    if "google_trends" in s or "psych" in s or "wvs" in s:
        return "psych"
    if "ecdc" in s or "epidemic" in s or "bio" in s:
        return "bio"
    if "eurobarometer" in s or "parlemeter" in s or "survey" in s:
        return "survey"
    if "real" in m or "canonical" in m:
        return "real_data"
    return "unknown"

def _evidence_strength(summary: Dict) -> str:
    v = _get_str(summary, "evidence_strength")
    if v:
        return v
    pd = summary.get("power_diagnostic")
    if isinstance(pd, dict):
        v2 = pd.get("evidence_strength") or pd.get("evidence")
        if isinstance(v2, str) and v2.strip():
            return v2.strip()
    return ""

def _all_pass(summary: Dict, stability: Dict) -> str:
    # Use stability if present
    sc = stability.get("stability_check")
    if isinstance(sc, dict) and "all_pass" in sc:
        return str(bool(sc.get("all_pass")))
    if "all_pass" in summary:
        return str(bool(summary.get("all_pass")))
    return ""

def _manifest_sha256(manifest: Dict) -> str:
    v = _get_str(manifest, "manifest_sha256", "sha256")
    return v

def _criteria_sha256(stability: Dict) -> str:
    return _get_str(stability, "criteria_sha256")

def _commit_sha(summary: Dict) -> str:
    return _get_str(summary, "commit_sha", "head_sha", "sha", "git_sha")

def _workflow_source(summary: Dict, fallback: str = "") -> str:
    return _get_str(summary, "workflow_source", "workflow_name", "workflow") or fallback

# Aliases expected by tests
def _get_commit_sha(summary: Dict) -> str:
    return _commit_sha(summary)

def _get_dataset_id(summary: Dict) -> str:
    return _dataset_id(summary)

def _get_evidence_strength(summary: Dict) -> str:
    return _evidence_strength(summary)

def _infer_run_mode(summary: Dict, has_stability: bool) -> str:
    return _run_mode(summary, has_stability)

def _infer_sector(dataset_id_or_summary, run_mode: str = "") -> str:
    """Wrapper: accept (dataset_id, run_mode) strings or (summary, dataset_id, run_mode)."""
    if isinstance(dataset_id_or_summary, dict):
        return _sector(dataset_id_or_summary, "", run_mode)
    return _sector({}, dataset_id_or_summary, run_mode)

def _existing_keys(path: Path) -> set:
    keys=set()
    with path.open("r", encoding="utf-8", newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            keys.add((row.get("github_run_id",""), row.get("run_dir_name",""), row.get("dataset_id","")))
    return keys

def _find_summary_paths(in_dir: Path) -> List[Path]:
    hits=[]
    for p in in_dir.rglob("summary.json"):
        # Expect .../runs/<ts>/tables/summary.json
        if p.parent.name == "tables" and p.name == "summary.json" and p.parents[2].name == "runs":
            hits.append(p)
    return sorted(set(hits))

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--append", action="store_true")
    args=ap.parse_args()

    in_dir=Path(args.in_dir)
    out_dir=Path(args.out_dir)

    runs_index = out_dir/"runs_index.csv"
    history = out_dir/"history.csv"

    _ensure_csv_with_header(runs_index, RUNS_INDEX_FIELDS)
    _ensure_csv_with_header(history, HISTORY_FIELDS)

    summaries=_find_summary_paths(in_dir)
    if not summaries:
        print(f"[INFO] No runs found under {in_dir}")
        return

    existing=_existing_keys(runs_index) if args.append else set()
    now = datetime.now(timezone.utc).isoformat()

    idx_rows=[]
    hist_rows=[]

    for sp in summaries:
        summary=_read_json(sp) or {}
        run_dir=sp.parents[1]
        stability_path=run_dir/"stability"/"stability_summary.json"
        manifest_path=run_dir/"manifest.json"

        stability=_read_json(stability_path) or {}
        manifest=_read_json(manifest_path) or {}

        has_stability=stability_path.exists()

        gid=_infer_github_run_id(sp)
        rname=_infer_run_dir_name(sp)
        did=_dataset_id(summary)
        mode=_run_mode(summary, has_stability)
        sector=_sector(summary, did, mode)
        ev=_evidence_strength(summary)
        apass=_all_pass(summary, stability)
        msha=_manifest_sha256(manifest)
        csha=_criteria_sha256(stability)
        cmt=_commit_sha(summary)
        wsrc=_workflow_source(summary)
        # Override workflow_source from run_meta.json if available
        run_meta_path = sp.parents[3] / "run_meta.json"
        run_meta = _read_json(run_meta_path) or {}
        if run_meta.get("workflowName"):
            wsrc = run_meta["workflowName"]

        key=(gid, rname, did)
        if args.append and key in existing:
            continue

        row={
            "github_run_id": gid,
            "run_dir_name": rname,
            "dataset_id": did,
            "sector": sector,
            "run_mode": mode,
            "evidence_strength": ev,
            "all_pass": apass,
            "manifest_sha256": msha,
            "stability_criteria_sha256": csha,
            "commit_sha": cmt,
            "workflow_source": wsrc,
        }
        idx_rows.append(row)
        hist_rows.append({"timestamp": now, **row})

    if idx_rows:
        with runs_index.open("a", encoding="utf-8", newline="") as f:
            w=csv.DictWriter(f, fieldnames=RUNS_INDEX_FIELDS)
            for r in idx_rows:
                w.writerow({k: r.get(k,"") for k in RUNS_INDEX_FIELDS})

        with history.open("a", encoding="utf-8", newline="") as f:
            w=csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
            for r in hist_rows:
                w.writerow({k: r.get(k,"") for k in HISTORY_FIELDS})

    print(f"[INFO] Appended {len(idx_rows)} rows.")

if __name__ == "__main__":
    main()
