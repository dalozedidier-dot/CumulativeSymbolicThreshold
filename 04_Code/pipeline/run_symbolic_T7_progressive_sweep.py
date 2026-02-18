#!/usr/bin/env python3
# 04_Code/pipeline/run_symbolic_T7_progressive_sweep.py
"""
Test T7 (normatif) : variation progressive de S -> apparition d'un point de bascule stable (S*).
Objectif : produire une courbe C_end(S) et tester linéaire vs piecewise, avec estimation de S*.

Outputs (dans --outdir):
- figures/t7_C_end_vs_S.png
- tables/sweep_results.csv
- tables/summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_Code"))

from pipeline.ori_c_pipeline import ORICConfig, generate_oric_synth  # noqa: E402


def _fit_linear(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    rss = float(np.sum((y - yhat) ** 2))
    return beta, rss


def _fit_piecewise_grid(x: np.ndarray, y: np.ndarray, candidates: List[float]) -> Dict:
    best = {"bic": float("inf")}
    n = len(x)
    for c in candidates:
        x2 = np.maximum(0.0, x - c)
        X = np.column_stack([np.ones_like(x), x, x2])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        yhat = X @ beta
        rss = float(np.sum((y - yhat) ** 2))
        rss = max(rss, 1e-12)
        k = 3
        bic = n * np.log(rss / n) + k * np.log(n)
        if bic < best["bic"]:
            best = {"c": float(c), "beta": beta.tolist(), "rss": rss, "bic": float(bic)}
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=str, required=True)
    ap.add_argument("--seed", type=int, default=9090)
    ap.add_argument("--n", type=int, default=40, help="runs per S level")
    ap.add_argument("--t-steps", type=int, default=260)
    ap.add_argument("--levels", type=str, default="0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0")
    ap.add_argument("--symbolic-threshold", type=float, default=0.50, help="ground-truth threshold used in generator")
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--delta-bic-min", type=float, default=10.0, help="min ΔBIC to favor piecewise")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    (outdir / "figures").mkdir(parents=True, exist_ok=True)
    (outdir / "tables").mkdir(parents=True, exist_ok=True)

    levels = [float(s.strip()) for s in args.levels.split(",") if s.strip()]
    levels = sorted(levels)

    base_cfg = ORICConfig(
        t_steps=int(args.t_steps),
        demand_base=1.0,
        demand_shock=0.0,
        cap_scale=1.0,
        omega=1.0,
        alpha=0.10,
        delta_window=10,
        threshold_k=2.5,
        threshold_m=3,
        symbolic_threshold=float(args.symbolic_threshold),
        symbolic_target=0.0,
        symbolic_cut=False,
        symbolic_cut_start=0,
        symbolic_injection_start=None,
        symbolic_injection_strength=0.0,
    )

    rows = []
    for j, s0 in enumerate(levels):
        cfg = ORICConfig(**{**asdict(base_cfg), "symbolic_target": float(s0)})
        for i in range(args.n):
            df = generate_oric_synth(cfg, seed=args.seed + j * 100000 + i)
            rows.append(
                {
                    "S_level": float(s0),
                    "seed": int(args.seed + j * 100000 + i),
                    "C_end": float(df["C"].iloc[-1]),
                    "S_end": float(df["S"].iloc[-1]),
                    "Sigma_mean": float(df["Sigma"].mean()),
                    "V_q05": float(np.quantile(df["V"].values, 0.05)),
                }
            )

    df_all = pd.DataFrame(rows)
    df_all.to_csv(outdir / "tables" / "sweep_results.csv", index=False)

    g = df_all.groupby("S_level")["C_end"].agg(["mean", "std", "count"]).reset_index()
    x = g["S_level"].values.astype(float)
    y = g["mean"].values.astype(float)

    lin_beta, lin_rss = _fit_linear(x, y)
    n = len(x)
    lin_bic = n * np.log(max(lin_rss, 1e-12) / n) + 2 * np.log(n)

    candidates = [c for c in x[1:-1]]  # exclude ends
    pw = _fit_piecewise_grid(x, y, candidates) if len(candidates) >= 2 else {"bic": float("inf")}
    delta_bic = float(lin_bic - pw["bic"]) if pw.get("bic", float("inf")) < float("inf") else float("-inf")
    prefer_piecewise = bool(delta_bic >= float(args.delta_bic_min))

    verdict = "INDETERMINATE"
    if prefer_piecewise:
        verdict = "ACCEPT"
    else:
        verdict = "REJECT"

    summary = {
        "test_id": "T7_progressive_S_to_C_threshold",
        "n_per_level": int(args.n),
        "levels": levels,
        "symbolic_threshold_generator": float(args.symbolic_threshold),
        "linear_bic": float(lin_bic),
        "piecewise_best": pw,
        "delta_bic_linear_minus_piecewise": float(delta_bic),
        "delta_bic_min": float(args.delta_bic_min),
        "prefer_piecewise": prefer_piecewise,
        "verdict": verdict,
        "notes": "T7 detects a stable breakpoint S* via BIC comparison on mean C_end(S).",
    }
    (outdir / "tables" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    # plot
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.errorbar(x, y, yerr=g["std"].values, fmt="o-", capsize=3, label="mean ± sd")
    ax.set_xlabel("S level (target)")
    ax.set_ylabel("C_end (mean)")
    ax.set_title("T7: Progressive S sweep -> C_end and piecewise fit")

    # linear fit line
    xx = np.linspace(x.min(), x.max(), 200)
    yy_lin = lin_beta[0] + lin_beta[1] * xx
    ax.plot(xx, yy_lin, linestyle="--", label="linear fit")

    if prefer_piecewise and "c" in pw:
        c = pw["c"]
        beta = np.array(pw["beta"], dtype=float)
        yy_pw = beta[0] + beta[1] * xx + beta[2] * np.maximum(0.0, xx - c)
        ax.plot(xx, yy_pw, linestyle="-.", label=f"piecewise fit (S*≈{c:.2f})")
        ax.axvline(c, linestyle=":")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "figures" / "t7_C_end_vs_S.png", dpi=200)
    plt.close(fig)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
