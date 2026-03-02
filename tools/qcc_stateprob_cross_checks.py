#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path

REQUIRED_REL = [
  "tables/inventory.csv",
  "tables/recommendations.json",
  "tables/selected_plan.json",
  "tables/ccl_points.csv",
  "tables/ccl_by_shots.csv",
  "tables/tstar_by_shots.csv",
  "tables/bootstrap_tstar_by_shots.csv",
  "tables/summary.json",
  "figures/ccl_vs_axis_by_shots.png",
  "figures/tstar_hist.png",
  "contracts/mapping_cross_conditions.json",
  "manifest.json",
]

def latest_run_dir(out_root: Path) -> Path:
    runs = out_root / "runs"
    if not runs.exists():
        raise FileNotFoundError(f"No runs directory: {runs}")
    candidates = [p for p in runs.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No run dirs under: {runs}")
    return sorted(candidates)[-1]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", "--out-dir", dest="out_root", required=True)
    args = ap.parse_args()
    out_root = Path(args.out_root)
    run_dir = latest_run_dir(out_root)

    missing = [rel for rel in REQUIRED_REL if not (run_dir / rel).exists()]
    if missing:
        print(f"Missing required outputs: {missing}")
        return 1

    # Manifest coverage: ensure every required file except manifest itself is in entries
    mani = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    entries = mani.get("entries", {})
    need = [rel for rel in REQUIRED_REL if rel != "manifest.json"]
    missing_entries = [rel for rel in need if rel not in entries]
    if missing_entries:
        print(f"Manifest missing entries: {missing_entries}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
