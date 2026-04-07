#!/usr/bin/env python3
"""04_Code/pipeline/run_multiscale.py

Multi-scale temporal analysis: run ORI-C at monthly, quarterly, annual scales.

Usage:
  python 04_Code/pipeline/run_multiscale.py --all --outdir 05_Results/multiscale/
  python 04_Code/pipeline/run_multiscale.py --help
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
REAL_DATA_SCRIPT = str(_REPO / "04_Code" / "pipeline" / "run_real_data_demo.py")

SEED = 8000
SCALES = {
    "monthly": 1,       # native (no aggregation)
    "quarterly": 3,     # mean of 3 consecutive months
    "annual": 12,       # mean of 12 consecutive months
}


def _discover_datasets(root: Path) -> list[Path]:
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            datasets.append(p.parent)
    return datasets


def _aggregate(df: pd.DataFrame, factor: int) -> pd.DataFrame:
    """Aggregate time series by factor (mean of consecutive rows)."""
    if factor <= 1:
        return df.copy()

    n = len(df)
    n_groups = n // factor
    if n_groups < 10:
        return df.copy()

    cols = ["O", "R", "I", "demand", "S"]
    available = [c for c in cols if c in df.columns]

    rows = []
    for g in range(n_groups):
        start = g * factor
        end = start + factor
        chunk = df.iloc[start:end]
        row = {"t": g}
        for c in available:
            vals = pd.to_numeric(chunk[c], errors="coerce")
            row[c] = float(vals.mean())
        # Preserve year/month from first row if available
        if "year" in df.columns:
            row["year"] = int(chunk["year"].iloc[0])
        if "month" in df.columns:
            row["month"] = int(chunk["month"].iloc[0])
        rows.append(row)

    return pd.DataFrame(rows)


def _run_oric(csv_path: Path, outdir: Path) -> dict:
    """Run ORI-C and return summary."""
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, REAL_DATA_SCRIPT,
        "--input", str(csv_path),
        "--outdir", str(outdir),
        "--time-mode", "index",
        "--normalize", "robust",
        "--control-mode", "no_symbolic",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    summary = {"verdict": "ERROR", "threshold_hit_idx": None, "n_steps": 0}
    sp = outdir / "tables" / "summary.json"
    if sp.exists():
        try:
            s = json.loads(sp.read_text())
            summary["verdict"] = s.get("verdict", "ERROR")
            summary["threshold_hit_idx"] = s.get("threshold_hit_idx")
            summary["n_steps"] = s.get("n_steps", 0)
            summary["C_mean"] = s.get("C_mean", 0)
        except Exception:
            pass
    return summary


def analyze_dataset(ds_dir: Path, outdir: Path) -> dict | None:
    """Run ORI-C at 3 scales for one dataset."""
    csv_path = ds_dir / "real.csv"
    df = pd.read_csv(csv_path)
    ds_id = ds_dir.name
    n = len(df)

    if n < 24:  # need at least 2 annual points
        return None

    result = {"dataset_id": ds_id, "original_n": n, "scales": {}}

    for scale_name, factor in SCALES.items():
        df_agg = _aggregate(df, factor)
        n_agg = len(df_agg)

        if n_agg < 15:
            result["scales"][scale_name] = {
                "n": n_agg, "verdict": "SKIP", "note": "Too few points after aggregation"
            }
            continue

        # Save aggregated CSV
        scale_dir = outdir / ds_id / scale_name
        scale_dir.mkdir(parents=True, exist_ok=True)
        agg_csv = scale_dir / "real_agg.csv"
        df_agg.to_csv(agg_csv, index=False)

        # Run ORI-C
        run_dir = scale_dir / "run"
        summary = _run_oric(agg_csv, run_dir)
        summary["n"] = n_agg
        summary["scale"] = scale_name
        result["scales"][scale_name] = summary

    # Coherence analysis
    verdicts = {s: info.get("verdict") for s, info in result["scales"].items()}
    result["verdict_coherent"] = len(set(v for v in verdicts.values() if v not in ("SKIP", "ERROR"))) <= 1

    # Detection point comparison (relative position)
    for scale_name, info in result["scales"].items():
        hit = info.get("threshold_hit_idx")
        n_scale = info.get("n", 1)
        if hit is not None and n_scale > 0:
            info["relative_detection_position"] = float(hit) / max(n_scale, 1)

    # Save per-dataset results
    ds_out = outdir / ds_id
    ds_out.mkdir(parents=True, exist_ok=True)
    (ds_out / "multiscale_results.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-scale temporal analysis")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=str, default=None)
    ap.add_argument("--outdir", default="05_Results/multiscale/")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.dataset:
        datasets = [Path(args.dataset)]
    elif args.all:
        datasets = _discover_datasets(_REPO / "03_Data")
    else:
        ap.print_help()
        return 1

    print(f"Found {len(datasets)} datasets")

    all_results = []
    for i, ds in enumerate(datasets):
        print(f"[{i+1}/{len(datasets)}] {ds.name}...")
        try:
            result = analyze_dataset(ds, outdir)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Coherence CSV
    rows = []
    for r in all_results:
        for scale, info in r["scales"].items():
            rows.append({
                "dataset_id": r["dataset_id"],
                "scale": scale,
                "n": info.get("n", 0),
                "verdict": info.get("verdict", "?"),
                "threshold_hit_idx": info.get("threshold_hit_idx"),
                "relative_position": info.get("relative_detection_position"),
            })

    if rows:
        pd.DataFrame(rows).to_csv(outdir / "multiscale_coherence.csv", index=False)

    # Summary JSON
    (outdir / "multiscale_summary.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8")

    n_coherent = sum(1 for r in all_results if r.get("verdict_coherent", False))
    print(f"\nDone. {n_coherent}/{len(all_results)} datasets show cross-scale coherence.")
    print(f"Results in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
