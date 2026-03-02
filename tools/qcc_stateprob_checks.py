#!/usr/bin/env python3
"""
Non-interpretive checks for QCC StateProb Bootstrap.

We enforce:
- presence of core outputs
- presence of inventory + recommendations (requested)
- basic CSV sanity (non-empty headers)
No verdicts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


REQUIRED_TABLES = [
    "tables/ccl_timeseries.csv",
    "tables/tstar_by_instance.csv",
    "tables/bootstrap_tstar.csv",
    "tables/summary.json",
    "tables/inventory.csv",
    "tables/recommendations.json",
]


REQUIRED_FIGURES_ANY = [
    "figures/ccl_mean.png",
    "figures/tstar_hist.png",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    missing = []
    for rel in REQUIRED_TABLES:
        if not (run_dir / rel).exists():
            missing.append(rel)

    if missing:
        raise SystemExit(f"Missing required outputs: {missing}")

    # At least one figure should exist (some runs may not generate hist if no t* values)
    if not any((run_dir / p).exists() for p in REQUIRED_FIGURES_ANY):
        raise SystemExit(f"Missing figures; expected at least one of: {REQUIRED_FIGURES_ANY}")

    # Sanity: inventory has expected columns
    inv = pd.read_csv(run_dir / "tables/inventory.csv")
    for c in ["algo", "device", "shots", "n_pairs", "n_instances", "depth_distinct_median"]:
        if c not in inv.columns:
            raise SystemExit(f"inventory.csv missing column: {c}")

    # recommendations is valid json with top10 list
    rec = json.loads((run_dir / "tables/recommendations.json").read_text(encoding="utf-8"))
    if "top10" not in rec or not isinstance(rec["top10"], list):
        raise SystemExit("recommendations.json invalid structure: expected key top10 as list")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
