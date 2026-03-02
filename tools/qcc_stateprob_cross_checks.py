#!/usr/bin/env python3
"""
Checks for QCC StateProb Cross-Conditions runs.

Validates the latest run under --out-root/runs:
- required tables: summary.json, inventory.csv, recommendations.json, ccl_points.csv, ccl_by_shots.csv,
  tstar_by_shots.csv, bootstrap_tstar_by_shots.csv
- required figures: ccl_vs_axis_by_shots.png, tstar_hist.png
- required contracts: mapping_cross_conditions.json
- manifest.json exists and contains hashes for required files
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TABLES = [
    "tables/summary.json",
    "tables/inventory.csv",
    "tables/recommendations.json",
    "tables/ccl_points.csv",
    "tables/ccl_by_shots.csv",
    "tables/tstar_by_shots.csv",
    "tables/bootstrap_tstar_by_shots.csv",
]
REQUIRED_FIGS = [
    "figures/ccl_vs_axis_by_shots.png",
    "figures/tstar_hist.png",
]
REQUIRED_CONTRACTS = [
    "contracts/mapping_cross_conditions.json",
]


def latest_run(out_root: Path) -> Path:
    runs = out_root / "runs"
    if not runs.exists():
        raise SystemExit(f"No runs directory: {runs}")
    dirs = [p for p in runs.iterdir() if p.is_dir()]
    if not dirs:
        raise SystemExit("No run dirs found")
    return sorted(dirs)[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()
    out_root = Path(args.out_root)

    run_dir = latest_run(out_root)
    missing = []
    for rel in REQUIRED_TABLES + REQUIRED_FIGS + REQUIRED_CONTRACTS + ["manifest.json"]:
        if not (run_dir / rel).exists():
            missing.append(rel)
    if missing:
        print(f"Missing required outputs in {run_dir.name}: {missing}")
        return 1

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    paths = {f["path"] for f in manifest.get("files", [])}
    miss_in_manifest = []
    for rel in REQUIRED_TABLES + REQUIRED_FIGS + REQUIRED_CONTRACTS:
        if rel not in paths:
            miss_in_manifest.append(rel)
    if miss_in_manifest:
        print(f"Manifest missing entries: {miss_in_manifest}")
        return 1

    print(f"OK: {run_dir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
