#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    runs_dir = out_dir / "runs"
    if not runs_dir.exists():
        raise SystemExit("Missing runs/ directory")

    # latest run
    runs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    if not runs:
        raise SystemExit("No run directories found")
    run = runs[-1]

    tables = run / "tables"
    figs = run / "figures"
    contracts = run / "contracts"

    required_tables = ["ccl_timeseries.csv", "tstar_by_instance.csv", "bootstrap_tstar.csv", "summary.json", "inventory.csv", "recommendations.json"]
    for f in required_tables:
        if not (tables / f).exists():
            raise SystemExit(f"Missing table: {f}")

    # recommendations.json must contain topk
    rec = json.loads((tables / "recommendations.json").read_text(encoding="utf-8"))
    if "topk" not in rec or not isinstance(rec["topk"], list):
        raise SystemExit("recommendations.json invalid: missing topk list")

    if not contracts.exists() or not (contracts / "mapping.json").exists():
        raise SystemExit("Missing contracts/mapping.json")

    if not figs.exists():
        raise SystemExit("Missing figures directory")
    pngs = list(figs.glob("*.png"))
    if not pngs:
        raise SystemExit("No PNG figures generated")

    if not (run / "manifest.json").exists():
        raise SystemExit("Missing manifest.json")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
