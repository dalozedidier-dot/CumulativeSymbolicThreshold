#!/usr/bin/env python3
"""
04_Code/pipeline/run_robustness.py

Robustness sweep around the ORI-C threshold detector.

It varies omega and alpha_scale and records whether a threshold is detected.
This script depends on helpers provided by pipeline.run_synthetic_demo.

Note on --seed
- The current pipeline is deterministic from the input CSV.
- Seed is accepted for suite compatibility and future stochastic extensions.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import argparse
import json
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pipeline.run_synthetic_demo import (
    Weights,
    compute_capacity,
    compute_sigma,
    compute_V,
    compute_S,
    compute_C_simplified,
    detect_threshold,
)


def _make_dirs(outdir: Path) -> tuple[Path, Path]:
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    return figdir, tabdir


def _apply_variant(df_raw: pd.DataFrame, omega: float, alpha_scale: float, cap_scale: float) -> pd.DataFrame:
    df = df_raw.copy()

    # capacity, sigma
    df["Cap"] = compute_capacity(df, scale=cap_scale)
    df["Sigma"] = compute_sigma(df)

    w = Weights()
    df["V"] = compute_V(df, w)
    df["S"] = compute_S(df, w)

    # Variant knobs:
    # - omega: amplifies mismatch contribution into symbolic perturbation proxy
    # - alpha_scale: scales sigma->S coupling by mixing sigma into S as a weak perturbation
    if "perturb_symbolic" not in df.columns:
        df["perturb_symbolic"] = 0.0
    df["perturb_symbolic"] = df["perturb_symbolic"].astype(float) + omega * (df["Sigma"] / (df["Sigma"].max() + 1e-12))

    # Simple C
    df["C"] = compute_C_simplified(df)

    # optional: make C slightly more sensitive to symbolic perturbation
    df["C"] = df["C"] + alpha_scale * df["perturb_symbolic"].cumsum().to_numpy()

    df["delta_C"] = df["C"].diff().fillna(0.0)
    return df


def _plot_heatmap(results: pd.DataFrame, figdir: Path) -> None:
    pivot = results.pivot(index="omega", columns="alpha_scale", values="threshold_detected").astype(float)
    plt.figure(figsize=(9, 6))
    plt.imshow(pivot.values, aspect="auto", origin="lower")
    plt.xticks(range(len(pivot.columns)), [f"{c:.2f}" for c in pivot.columns], rotation=45)
    plt.yticks(range(len(pivot.index)), [f"{i:.2f}" for i in pivot.index])
    plt.xlabel("alpha_scale")
    plt.ylabel("omega")
    plt.title("Threshold detected (1) across variants")
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(figdir / "threshold_detected_heatmap.png", dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input synthetic CSV")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=123, help="Accepted for suite compatibility (no effect today)")
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=30)
    ap.add_argument("--cap-scale", type=float, default=1000.0)
    ap.add_argument("--omegas", default="0.0,0.25,0.5,0.75,1.0")
    ap.add_argument("--alphas", default="0.0,0.10,0.20,0.30,0.40,0.50")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    df_raw = pd.read_csv(Path(args.input))
    if "t" not in df_raw.columns:
        df_raw["t"] = np.arange(len(df_raw), dtype=int)

    omegas = [float(x.strip()) for x in str(args.omegas).split(",") if x.strip()]
    alphas = [float(x.strip()) for x in str(args.alphas).split(",") if x.strip()]

    rows: List[Dict] = []
    for omega in omegas:
        for alpha_scale in alphas:
            df = _apply_variant(df_raw, omega=omega, alpha_scale=alpha_scale, cap_scale=float(args.cap_scale))
            thr_idx, thr_val = detect_threshold(df["delta_C"], k=float(args.k), m=int(args.m), baseline_n=int(args.baseline_n))
            detected = thr_idx is not None

            rows.append(
                {
                    "omega": omega,
                    "alpha_scale": alpha_scale,
                    "k": float(args.k),
                    "m": int(args.m),
                    "baseline_n": int(args.baseline_n),
                    "threshold_detected": bool(detected),
                    "threshold_value": float(thr_val),
                    "threshold_index": None if thr_idx is None else int(thr_idx),
                }
            )

    results = pd.DataFrame(rows)
    results.to_csv(tabdir / "robustness_results.csv", index=False)

    share = float((results["threshold_detected"] == True).mean())  # noqa: E712
    verdict = "ACCEPT" if share >= 0.80 else ("REJECT" if share <= 0.20 else "INDETERMINATE")

    summary = {
        "input": str(args.input),
        "n": int(len(df_raw)),
        "seed": int(args.seed),
        "omegas": omegas,
        "alphas": alphas,
        "k": float(args.k),
        "m": int(args.m),
        "baseline_n": int(args.baseline_n),
        "share_threshold_detected": share,
        "verdict": verdict,
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    (tabdir / "verdict.json").write_text(
        json.dumps(
            {
                "test": "robustness_threshold",
                "verdict": verdict,
                "share_threshold_detected": share,
                "k": float(args.k),
                "m": int(args.m),
                "baseline_n": int(args.baseline_n),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _plot_heatmap(results, figdir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
