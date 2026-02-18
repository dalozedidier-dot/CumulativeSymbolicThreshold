#!/usr/bin/env python3
# 04_Code/pipeline/run_symbolic_T4_s_rich_poor.py
"""
Test T4 (normatif) : Variation contrôlée de S(t) -> effet sur C(t), à ORI comparable.
Objectif : comparer C(t) sous condition S_rich vs S_poor, sans exiger Σ>0.

Outputs (dans --outdir):
- figures/t4_s_rich_poor_c_end.png
- tables/summary.csv
- tables/summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind

# Robust sys.path: allow "import pipeline.*" when executed as a file
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_Code"))

from pipeline.ori_c_pipeline import ORICConfig, generate_oric_synth  # noqa: E402


def _robust_sd(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    sd = 1.4826 * mad
    return float(sd) if sd > 1e-12 else float(np.std(x, ddof=1) + 1e-12)


def _bootstrap_ci(delta: np.ndarray, n_boot: int, seed: int) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    boots = []
    n = len(delta)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots.append(float(np.mean(delta[idx])))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def run_condition(cfg: ORICConfig, n: int, seed: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        df = generate_oric_synth(cfg, seed=seed + i)
        rows.append(
            {
                "seed": seed + i,
                "C_end": float(df["C"].iloc[-1]),
                "S_end": float(df["S"].iloc[-1]),
                "Sigma_mean": float(df["Sigma"].mean()),
                "V_q05": float(np.quantile(df["V"].values, 0.05)),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=str, required=True)
    ap.add_argument("--n", type=int, default=60, help="runs per condition")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--t-steps", type=int, default=260)
    ap.add_argument("--s-poor", type=float, default=0.15)
    ap.add_argument("--s-rich", type=float, default=0.80)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--sesoi-sd", type=float, default=0.30, help="SESOI in robust SD units for C")
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    (outdir / "figures").mkdir(parents=True, exist_ok=True)
    (outdir / "tables").mkdir(parents=True, exist_ok=True)

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
        symbolic_threshold=None,  # no forced threshold for T4
        symbolic_target=0.0,
        symbolic_cut=False,
        symbolic_cut_start=0,
        symbolic_injection_start=None,
        symbolic_injection_strength=0.0,
    )

    cfg_poor = ORICConfig(**{**asdict(base_cfg), "symbolic_target": float(args.s_poor)})
    cfg_rich = ORICConfig(**{**asdict(base_cfg), "symbolic_target": float(args.s_rich)})

    df_poor = run_condition(cfg_poor, n=args.n, seed=args.seed + 10000)
    df_rich = run_condition(cfg_rich, n=args.n, seed=args.seed + 20000)

    poor = df_poor["C_end"].values
    rich = df_rich["C_end"].values

    delta = rich.mean() - poor.mean()
    sd = _robust_sd(np.concatenate([poor, rich]))
    effect_sd = float(delta / sd)

    # Welch t-test
    tstat, pval = ttest_ind(rich, poor, equal_var=False)

    # bootstrap CI for delta
    rng = np.random.default_rng(args.seed)
    boot_deltas = []
    for _ in range(args.n_boot):
        boot_r = rng.choice(rich, size=len(rich), replace=True)
        boot_p = rng.choice(poor, size=len(poor), replace=True)
        boot_deltas.append(float(np.mean(boot_r) - np.mean(boot_p)))
    ci_lo, ci_hi = np.percentile(boot_deltas, [2.5, 97.5])
    ci_lo, ci_hi = float(ci_lo), float(ci_hi)

    verdict = "INDETERMINATE"
    if (pval <= args.alpha) and (effect_sd >= args.sesoi_sd) and (ci_lo > 0.0):
        verdict = "ACCEPT"
    elif (pval <= args.alpha) and (ci_hi < 0.0):
        verdict = "REJECT"

    summary = {
        "test_id": "T4_symbolic_S_rich_vs_poor_on_C",
        "n_per_condition": int(args.n),
        "alpha": float(args.alpha),
        "sesoi_sd": float(args.sesoi_sd),
        "C_end_mean_poor": float(poor.mean()),
        "C_end_mean_rich": float(rich.mean()),
        "delta_C_end": float(delta),
        "effect_sd": float(effect_sd),
        "ci95_delta_lo": ci_lo,
        "ci95_delta_hi": ci_hi,
        "p_value_welch": float(pval),
        "verdict": verdict,
        "notes": "T4 tests S->C with ORI fixed; Σ not required to be >0.",
    }

    pd.DataFrame([summary]).to_csv(outdir / "tables" / "summary.csv", index=False)
    (outdir / "tables" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    # plot
    fig = plt.figure(figsize=(7, 4))
    ax = fig.add_subplot(111)
    ax.boxplot([poor, rich], labels=["S_poor", "S_rich"], showmeans=True)
    ax.set_ylabel("C_end")
    ax.set_title("T4: Controlled S variation -> C_end")
    fig.tight_layout()
    fig.savefig(outdir / "figures" / "t4_s_rich_poor_c_end.png", dpi=200)
    plt.close(fig)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
