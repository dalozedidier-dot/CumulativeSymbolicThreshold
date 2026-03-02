from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED = [
  "tables/inventory.csv",
  "tables/recommendations.json",
  "tables/ccl_points.csv",
  "tables/ccl_by_shots.csv",
  "tables/tstar_by_shots.csv",
  "tables/bootstrap_tstar_by_shots.csv",
  "contracts/mapping_cross_conditions.json",
  "manifest.json",
  "figures/ccl_vs_axis_by_shots.png",
]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Root output dir containing runs/")
    args = ap.parse_args()
    root = Path(args.out_root)
    runs = sorted((root / "runs").glob("*"))
    if not runs:
        raise SystemExit("No runs found under out root")
    latest = runs[-1]
    missing = [p for p in REQUIRED if not (latest / p).exists()]
    if missing:
        raise SystemExit(f"Missing required outputs: {missing}")
    man = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
    paths = {it["path"] for it in man.get("items", [])}
    man_missing = [p for p in REQUIRED if p not in paths]
    if man_missing:
        raise SystemExit(f"Manifest missing entries: {man_missing}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
