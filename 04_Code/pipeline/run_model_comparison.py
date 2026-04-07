#!/usr/bin/env python3
"""04_Code/pipeline/run_model_comparison.py

Compare 4 C(t) model variants (V1-V4) across all real datasets.

Usage:
  python 04_Code/pipeline/run_model_comparison.py --all --outdir 05_Results/model_comparison/
  python 04_Code/pipeline/run_model_comparison.py --help
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
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_CODE = Path(__file__).resolve().parents[1]
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from oric.ori_core_v2 import (  # noqa: E402
    ModelV2Config, compare_all_variants, run_variant_on_dataframe,
)
from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402

SEED = 8000
REAL_DATA_SCRIPT = str(_REPO / "04_Code" / "pipeline" / "run_real_data_demo.py")


def _discover_datasets(root: Path) -> list[Path]:
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            datasets.append(p.parent)
    return datasets


def _robust_minmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    finite = np.isfinite(x)
    if not finite.any():
        return np.zeros_like(x)
    lo = float(np.quantile(x[finite], 0.02))
    hi = float(np.quantile(x[finite], 0.98))
    if abs(hi - lo) < 1e-12:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def _prepare_sv_from_real(csv_path: Path) -> pd.DataFrame | None:
    """Load real.csv, run V1 pipeline to get S and V columns, return DataFrame."""
    df = pd.read_csv(csv_path)
    required = ["O", "R", "I"]
    for c in required:
        if c not in df.columns:
            return None

    n = len(df)
    if n < 20:
        return None

    # Normalize proxies
    for c in ["O", "R", "I"]:
        df[c] = _robust_minmax(pd.to_numeric(df[c], errors="coerce").fillna(0).values)

    if "demand" not in df.columns:
        df["demand"] = 0.9 * df["O"] * df["R"] * df["I"]
    else:
        df["demand"] = pd.to_numeric(df["demand"], errors="coerce").fillna(0).values

    if "S" not in df.columns:
        df["S"] = np.zeros(n)
    else:
        df["S"] = np.clip(pd.to_numeric(df["S"], errors="coerce").fillna(0).values, 0, 1)

    if "t" not in df.columns:
        df["t"] = np.arange(n)

    # Compute Cap, Sigma, V using the ORI-C mechanics
    Cap = df["O"].values * df["R"].values * df["I"].values * 1000.0
    demand_vals = df["demand"].values.astype(float)
    # Auto-scale demand
    if np.nanmedian(demand_vals) > 0:
        scale = np.nanmedian(Cap) / np.nanmedian(demand_vals[demand_vals > 0]) * 0.9
        demand_scaled = demand_vals * scale
    else:
        demand_scaled = 0.9 * Cap

    Sigma = np.maximum(0, demand_scaled - Cap)
    mismatch_frac = Sigma / (Cap + 1e-9)
    V = np.clip(1.0 - 1.2 * mismatch_frac, 0.0, 1.0)

    # Endogenous S if not provided
    S_vals = df["S"].values.copy()
    sigma_star = 0.0
    alpha_s = 0.0008
    s_decay = 0.002
    for t in range(1, n):
        sigma_symbolic = max(0, Sigma[t] - sigma_star)
        S_vals[t] = np.clip(S_vals[t] + alpha_s * sigma_symbolic - s_decay * S_vals[t], 0, 1)

    df["S"] = S_vals
    df["V"] = V
    df["Cap"] = Cap
    df["Sigma"] = Sigma
    return df


def process_dataset(dataset_dir: Path, outdir: Path, seed: int) -> dict | None:
    """Run 4 variants on a dataset, return comparison dict."""
    csv_path = dataset_dir / "real.csv"
    df = _prepare_sv_from_real(csv_path)
    if df is None:
        return None

    dataset_id = dataset_dir.name
    ds_outdir = outdir / dataset_id
    ds_outdir.mkdir(parents=True, exist_ok=True)

    comparison, df_all = compare_all_variants(df, seed=seed)

    # Save comparison table
    rows = []
    for variant, info in comparison.items():
        info["variant"] = variant
        info["dataset_id"] = dataset_id
        info["n_steps"] = len(df)
        rows.append(info)

    df_comp = pd.DataFrame(rows)
    df_comp.to_csv(ds_outdir / "comparison.csv", index=False)
    (ds_outdir / "comparison.json").write_text(
        json.dumps(comparison, indent=2, default=str), encoding="utf-8"
    )

    # Generate overlay figure
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    t = np.arange(len(df_all))
    colors = {"V1": "blue", "V2": "orange", "V3": "green", "V4": "red"}

    for variant in ["V1", "V2", "V3", "V4"]:
        c_col = f"C_{variant}"
        dc_col = f"delta_C_{variant}"
        if c_col in df_all.columns:
            axes[0].plot(t, df_all[c_col], label=variant, color=colors[variant], alpha=0.8)
            axes[1].plot(t, df_all[dc_col], label=variant, color=colors[variant], alpha=0.8)

    axes[0].set_ylabel("C(t)")
    axes[0].set_title(f"{dataset_id} — Model Comparison")
    axes[0].legend()
    axes[1].set_ylabel("delta_C(t)")
    axes[1].set_xlabel("t")
    axes[1].legend()
    plt.tight_layout()

    figdir = ds_outdir / "figures"
    figdir.mkdir(exist_ok=True)
    plt.savefig(figdir / "model_comparison_overlay.png", dpi=160)
    plt.close()

    return {"dataset_id": dataset_id, "comparison": comparison}


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare 4 C(t) model variants")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=str, default=None)
    ap.add_argument("--outdir", default="05_Results/model_comparison/")
    ap.add_argument("--seed", type=int, default=SEED)
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
            result = process_dataset(ds, outdir, args.seed + i)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Global comparison table
    rows = []
    for r in all_results:
        for variant, info in r["comparison"].items():
            rows.append({
                "dataset_id": r["dataset_id"],
                "variant": variant,
                "verdict": info["verdict"],
                "threshold_hit_idx": info["threshold_hit_idx"],
                "effect_size_d": info["effect_size_d"],
                "C_mean": info["C_mean"],
            })

    if rows:
        pd.DataFrame(rows).to_csv(outdir / "comparison_table.csv", index=False)

    # Summary JSON
    (outdir / "comparison_summary.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )

    print(f"\nDone. Results in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
