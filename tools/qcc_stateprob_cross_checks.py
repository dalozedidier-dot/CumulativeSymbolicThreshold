#!/usr/bin/env python3
"""Non-interpretative checks for QCC StateProb Cross-Conditions outputs.

Design goals:
- Strict on presence of expected output files in the latest run directory.
- Strict that manifest.json exists and *covers* the produced artifacts.
- Do NOT require manifest.json to list itself (a manifest cannot hash itself without recursion).
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
    "tables/selected_plan.json",
]
REQUIRED_FIGS = [
    "figures/ccl_vs_axis_by_shots.png",
    "figures/tstar_hist.png",
]
REQUIRED_CONTRACTS = [
    "contracts/mapping_cross_conditions.json",
]


def _latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.is_dir():
        raise FileNotFoundError(f"No runs directory: {runs_dir}")
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not run_dirs:
        raise FileNotFoundError(f"No run directories under: {runs_dir}")
    return sorted(run_dirs)[-1]


def _load_manifest(run_dir: Path) -> dict:
    mf = run_dir / "manifest.json"
    if not mf.exists():
        raise FileNotFoundError(f"Missing manifest file: {mf}")
    with mf.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Output root, e.g. _ci_out/qcc_stateprob_cross")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_dir = _latest_run_dir(out_root)

    missing_files: list[str] = []
    for rel in REQUIRED_TABLES + REQUIRED_FIGS + REQUIRED_CONTRACTS:
        if not (run_dir / rel).exists():
            missing_files.append(rel)

    if missing_files:
        print(f"Missing required outputs (in latest run {run_dir.name}): {missing_files}", file=sys.stderr)
        return 1

    manifest = _load_manifest(run_dir)
    entries = manifest.get("entries", {})

    # Required files must be present in manifest entries.
    expected_in_manifest = set(REQUIRED_TABLES + REQUIRED_FIGS + REQUIRED_CONTRACTS)
    missing_in_manifest = [p for p in sorted(expected_in_manifest) if p not in entries]

    # NOTE: We do NOT require 'manifest.json' to be inside entries.
    if missing_in_manifest:
        print(f"Manifest missing entries: {missing_in_manifest}", file=sys.stderr)
        return 1

    print(f"OK: latest run {run_dir.name} has required outputs and manifest coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
