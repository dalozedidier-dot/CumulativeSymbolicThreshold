\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def find_latest_run(out_root: Path) -> Path:
    runs = sorted([p for p in out_root.glob("run_*") if p.is_dir()])
    if not runs:
        raise SystemExit(f"No run_* directories found under {out_root}")
    return runs[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_dir = find_latest_run(out_root)

    tables = run_dir / "tables"
    figs = run_dir / "figures"
    manifest = run_dir / "manifest.json"

    required_paths = [
        tables / "events.csv",
        tables / "summary.json",
        manifest,
    ]
    for p in required_paths:
        if not p.exists():
            raise SystemExit(f"Missing required output: {p}")

    # Must have at least one timeseries_out_*.csv
    ts_files = sorted(tables.glob("timeseries_out_*.csv"))
    if not ts_files:
        raise SystemExit("No timeseries_out_*.csv files found")

    # Validate each timeseries file
    for f in ts_files:
        df = pd.read_csv(f)
        for col in ["t", "Cq", "O", "R", "Sigma"]:
            if col not in df.columns:
                raise SystemExit(f"Missing column {col} in {f.name}")
        # Sigma must be nondecreasing
        s = pd.to_numeric(df["Sigma"], errors="coerce").astype(float)
        if s.isna().any():
            raise SystemExit(f"NaN in Sigma for {f.name}")
        if (s.diff().fillna(0) < -1e-9).any():
            raise SystemExit(f"Sigma not nondecreasing in {f.name}")

    # Summary is parseable
    summary = json.loads((tables / "summary.json").read_text(encoding="utf-8"))
    if "params" not in summary:
        raise SystemExit("summary.json missing params")

    # Figures: optional per run, but if present, must include at least one png
    pngs = sorted(figs.glob("*.png"))
    if not pngs:
        # Do not fail hard, but keep check strict on contracts only
        print("Warning: no png figures found. Contracts still ok.")

    # Manifest must reference at least summary + events
    man = json.loads(manifest.read_text(encoding="utf-8"))
    paths = {x.get("path") for x in man.get("files", [])}
    must = {"tables/summary.json", "tables/events.csv"}
    if not must.issubset(paths):
        raise SystemExit(f"manifest.json missing required entries: {sorted(list(must - paths))}")

    print(f"QCC output check passed for {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
