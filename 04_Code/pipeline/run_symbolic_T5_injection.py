#!/usr/bin/env python3
# 04_Code/pipeline/run_symbolic_T5_injection.py
"""
Test T5 (normatif) : Injection symbolique à t0 -> effet différé mesurable sur C(t+T).
Objectif : comparer une condition injection vs contrôle, à ORI comparable.

Outputs (dans --outdir):
- figures/t5_injection_mean_C_t.png
- figures/t5_injection_C_end_box.png
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_Code"))

from pipeline.ori_c_pipeline import ORICConfig, generate_oric_synth  # noqa: E402


def _robust_sd(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    sd = 1.4826 * mad
    return float(sd) if sd > 1e-12 else float(np.std(x, ddof=1) + 1e-12)


def run_many(cfg: ORICConfig, n: int, seed: int) -> Tuple[pd.DataFrame, np.ndarray]:
    rows = []
    C_mat = []
    for i in range(n):
        df = generate_oric_synth(cfg, seed=seed + i)
        rows.append(
            {
                "seed": seed + i,
                "C_end": float(df["C"].iloc[-1]),
                "C_post": float(df["C"].iloc[int(cfg.t_steps * 0.6) :].mean()),
                "S_end": float(df["S"].iloc[-1]),
                "Sigma_mean": float(df["Sigma"].mean()),
                "V_q05": float(np.quantile(df["V"].values, 0.05)),
            }
        )
        C_mat.append(df["C"].values.astype(float))
    return pd.DataFrame(rows), np.vstack(C_mat)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=str, required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--t-steps", type=int, default=260)
    ap.add_argument("--t0", type=int, default=120)
    ap.add_argument("--s0", type=float, default=0.20, help="baseline symbolic_target")
    ap.add_argument("--inj", type=float, default=0.40, help="injection strength")
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--sesoi-sd", type=float, default=0.30)
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
        symbolic_threshold=None,
        symbolic_target=float(args.s0),
        symbolic_cut=False,
        symbolic_cut_start=0,
        symbolic_injection_start=None,
        symbolic_injection_strength=0.0,
    )

    cfg_ctrl = ORICConfig(**asdict(base_cfg))
    cfg_inj = ORICConfig(
        **{
            **asdict(base_cfg),
            "symbolic_injection_start": int(args.t0),
            "symbolic_injection_strength": float(args.inj),
        }
    )

    df_ctrl, C_ctrl = run_many(cfg_ctrl, n=args.n, seed=args.seed + 10000)
    df_inj, C_inj = run_many(cfg_inj, n=args.n, seed=args.seed + 20000)

    ctrl = df_ctrl["C_end"].values
    inj = df_inj["C_end"].values

    delta = float(inj.mean() - ctrl.mean())
    sd = _robust_sd(np.concatenate([ctrl, inj]))
    effect_sd = float(delta / sd)

    tstat, pval = ttest_ind(inj, ctrl, equal_var=False)

    # bootstrap CI
    rng = np.random.default_rng(args.seed)
    boots = []
    for _ in range(2000):
        b_inj = rng.choice(inj, size=len(inj), replace=True)
        b_ctrl = rng.choice(ctrl, size=len(ctrl), replace=True)
        boots.append(float(b_inj.mean() - b_ctrl.mean()))
    ci_lo, ci_hi = np.percentile(boots, [2.5, 97.5])
    ci_lo, ci_hi = float(ci_lo), float(ci_hi)

    verdict = "INDETERMINATE"
    if (pval <= args.alpha) and (effect_sd >= args.sesoi_sd) and (ci_lo > 0.0):
        verdict = "ACCEPT"
    elif (pval <= args.alpha) and (ci_hi < 0.0):
        verdict = "REJECT"

    summary = {
        "test_id": "T5_symbolic_injection_effect_on_C",
        "n_per_condition": int(args.n),
        "alpha": float(args.alpha),
        "sesoi_sd": float(args.sesoi_sd),
        "t0": int(args.t0),
        "s0": float(args.s0),
        "injection_strength": float(args.inj),
        "C_end_mean_control": float(ctrl.mean()),
        "C_end_mean_injection": float(inj.mean()),
        "delta_C_end": float(delta),
        "effect_sd": float(effect_sd),
        "ci95_delta_lo": ci_lo,
        "ci95_delta_hi": ci_hi,
        "p_value_welch": float(pval),
        "verdict": verdict,
        "notes": "T5 tests delayed effect of injection on C. Σ not required.",
    }

    pd.DataFrame([summary]).to_csv(outdir / "tables" / "summary.csv", index=False)
    (outdir / "tables" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    # plots
    t = np.arange(cfg_ctrl.t_steps)
    mean_ctrl = C_ctrl.mean(axis=0)
    mean_inj = C_inj.mean(axis=0)

    fig = plt.figure(figsize=(8, 4))
    ax = fig.add_subplot(111)
    ax.plot(t, mean_ctrl, label="control")
    ax.plot(t, mean_inj, label="injection")
    ax.axvline(args.t0, linestyle="--")
    ax.set_xlabel("t")
    ax.set_ylabel("C(t)")
    ax.set_title("T5: Mean C(t) control vs injection")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "figures" / "t5_injection_mean_C_t.png", dpi=200)
    plt.close(fig)

    fig2 = plt.figure(figsize=(7, 4))
    ax2 = fig2.add_subplot(111)
    ax2.boxplot([ctrl, inj], labels=["control", "injection"], showmeans=True)
    ax2.set_ylabel("C_end")
    ax2.set_title("T5: C_end distribution")
    fig2.tight_layout()
    fig2.savefig(outdir / "figures" / "t5_injection_C_end_box.png", dpi=200)
    plt.close(fig2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
