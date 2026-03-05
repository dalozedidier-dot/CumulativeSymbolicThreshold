#!/usr/bin/env python3
"""
repair_ci_metrics.py

Repairs ci_metrics/history.csv and ci_metrics/runs_index.csv when:
- duplicate header lines were appended in the middle,
- different schemas were appended (column drift),
- some workflows wrote a different column order.

Strategy:
- Parse with csv.reader (not DictReader) to keep raw rows.
- Detect header-like rows anywhere, drop them.
- Canonicalize each row to the strict schema using heuristics:
  - If row length matches strict, map by position.
  - If row matches known legacy schemas, remap.
  - Else, skip with report.

Outputs:
- runs_index_repaired.csv
- history_repaired.csv
- repair_report.json

Never overwrites originals.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

RUNS_INDEX_FIELDS = [
    "github_run_id","run_dir_name","dataset_id","sector","run_mode",
    "evidence_strength","all_pass","manifest_sha256","stability_criteria_sha256",
    "commit_sha","workflow_source",
]
HISTORY_FIELDS = ["timestamp"] + RUNS_INDEX_FIELDS

LEGACY_RUNS_SCHEMA_A = ["github_run_id","run_dir_name","dataset_id","sector","commit_sha","evidence_strength","all_pass","run_mode","manifest_sha256","stability_criteria_sha256","timestamp"]
# seen in your corrupted tail: github_run_id,run_dir_name,dataset_id,sector,commit_sha,evidence_strength,all_pass,canonical,manifest_sha256,criteria_sha256,timestamp

LEGACY_HISTORY_SCHEMA_A = ["timestamp","github_run_id","run_dir_name","dataset_id","sector","commit_sha","evidence_strength","all_pass","stability_criteria_sha256","run_mode","workflow"]

def is_header_row(row: List[str]) -> bool:
    if not row:
        return False
    joined=",".join([c.strip() for c in row])
    return joined == ",".join(RUNS_INDEX_FIELDS) or joined == ",".join(HISTORY_FIELDS) or "github_run_id" in row and "run_dir_name" in row and "dataset_id" in row and ("timestamp" in row)

def remap_row(row: List[str], schema: List[str], target: List[str]) -> Dict[str,str]:
    m={k:"" for k in target}
    for i,k in enumerate(schema):
        if i < len(row) and k in m:
            m[k]=row[i].strip()
    return m

def load_rows(path: Path) -> List[List[str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        r=csv.reader(f)
        return [row for row in r]

def write_csv(path: Path, fields: List[str], rows: List[Dict[str,str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k,"") for k in fields})

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--ci-metrics-dir", required=True)
    args=ap.parse_args()
    d=Path(args.ci_metrics_dir)

    runs_path=d/"runs_index.csv"
    hist_path=d/"history.csv"
    out_runs=d/"runs_index_repaired.csv"
    out_hist=d/"history_repaired.csv"
    report_path=d/"repair_report.json"

    report={"runs_index":{"kept":0,"dropped_headers":0,"skipped":0,"remapped_legacy":0},
            "history":{"kept":0,"dropped_headers":0,"skipped":0,"remapped_legacy":0},
            "skipped_examples":[]}

    # RUNS
    raw=load_rows(runs_path)
    # first row is header, but may be wrong; we still drop header-like rows everywhere
    repaired=[]
    for row in raw:
        if is_header_row(row):
            report["runs_index"]["dropped_headers"] += 1
            continue
        if len(row)==len(RUNS_INDEX_FIELDS):
            m=remap_row(row, RUNS_INDEX_FIELDS, RUNS_INDEX_FIELDS)
            repaired.append(m)
            report["runs_index"]["kept"] += 1
            continue
        # legacy schema A
        if len(row)==len(LEGACY_RUNS_SCHEMA_A):
            m=remap_row(row, LEGACY_RUNS_SCHEMA_A, RUNS_INDEX_FIELDS)
            # legacy had no workflow_source and run_mode sometimes in position 7
            if not m.get("run_mode") and len(row)>7:
                m["run_mode"]=row[7].strip()
            repaired.append(m)
            report["runs_index"]["kept"] += 1
            report["runs_index"]["remapped_legacy"] += 1
            continue
        report["runs_index"]["skipped"] += 1
        if len(report["skipped_examples"])<10:
            report["skipped_examples"].append({"file":"runs_index.csv","row":row})

    write_csv(out_runs, RUNS_INDEX_FIELDS, repaired)

    # HISTORY
    raw=load_rows(hist_path)
    repaired=[]
    for row in raw:
        if is_header_row(row):
            report["history"]["dropped_headers"] += 1
            continue
        if len(row)==len(HISTORY_FIELDS):
            m=remap_row(row, HISTORY_FIELDS, HISTORY_FIELDS)
            repaired.append(m)
            report["history"]["kept"] += 1
            continue
        # legacy schema A
        if len(row)==len(LEGACY_HISTORY_SCHEMA_A):
            m=remap_row(row, LEGACY_HISTORY_SCHEMA_A, HISTORY_FIELDS)
            repaired.append(m)
            report["history"]["kept"] += 1
            report["history"]["remapped_legacy"] += 1
            continue
        report["history"]["skipped"] += 1
        if len(report["skipped_examples"])<10:
            report["skipped_examples"].append({"file":"history.csv","row":row})

    write_csv(out_hist, HISTORY_FIELDS, repaired)

    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
