#!/usr/bin/env python3
"""ORI-C demo runner (control vs one intervention) with explicit, testable verdicts.

Minimal change policy:
- No theoretical rewrites.
- Only aligns the *tested metric* with the intended regime:
  - ORI-core interventions (demand_shock, capacity_hit): evaluate V under Sigma>0.
  - symbolic_cut: do not expect V movement when Sigma=0; evaluate C instead.

Outputs:
- 05_Results/<outdir>/{tables,figures}/
  - tables/control_timeseries.csv
  - tables/test_timeseries.csv
  - tables/summary.csv
  - figures/v_t_comparison.png
  - figures/<metric>_t_comparison.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

# Local import (repo layout)
from pipeline.ori_c_pipeline import generate_oric_synth


def scenario(
    *,
    n_steps: int,
    seed: int,
    intervention: str,
    t0: int,
    cap_scale: float,
    alpha: float,
    beta: float,
    gamma: float,
    demand_mult: float,
    demand_start: int,
    demand_duration: int,
) -> pd.DataFrame:
    df = generate_oric_synth(
        n_steps=n_steps,
        seed=seed,
        intervention=intervention,
        t0=t0,
        cap_scale=cap_scale,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        demand_mult=float(demand_mult),
        demand_start=int(demand_start),
        demand_duration=int(demand_duration),
    )
    return df


def _mkdirs(outdir: Path) -> tuple[Path, Path]:
    tabdir = outdir / "tables"
    figdir = outdir / "figures"
    tabdir.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)
    return tabdir, figdir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-steps", type=int, default=200)
    ap.add_argument("--t0", type=int, default=80)
    ap.add_argument("--cap-scale", type=float, default=1.0)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--beta", type=float, default=0.03)
    ap.add_argument("--gamma", type=float, default=0.08)
    ap.add_argument(
        "--intervention",
        default="demand_shock",
        choices=["none", "demand_shock", "symbolic_cut", "capacity_hit"],
    )
    ap.add_argument(
        "--metric",
        default="auto",
        choices=["auto", "V", "C"],
        help="Metric for verdict. auto = V for ORI-core, C for symbolic_cut.",
    )
    ap.add_argument("--alpha-level", type=float, default=0.01)
    ap.add_argument("--sesoi", type=float, default=0.05)

    # Demand shock knobs (forces Sigma>0 when testing V)
    ap.add_argument("--demand-mult", type=float, default=1.15)
    ap.add_argument("--demand-start", type=int, default=40)
    ap.add_argument("--demand-duration", type=int, default=40)

    args = ap.parse_args()

    metric_to_use = str(args.metric)
    if metric_to_use == "auto":
        metric_to_use = "C" if str(args.intervention) == "symbolic_cut" else "V"

    outdir = Path(args.outdir)
    tabdir, figdir = _mkdirs(outdir)

    df_control = scenario(
        n_steps=int(args.n_steps),
        seed=int(args.seed),
        intervention="none",
        t0=int(args.t0),
        cap_scale=float(args.cap_scale),
        alpha=float(args.alpha),
        beta=float(args.beta),
        gamma=float(args.gamma),
        demand_mult=float(args.demand_mult),
        demand_start=int(args.demand_start),
        demand_duration=int(args.demand_duration),
    )
    df_test = scenario(
        n_steps=int(args.n_steps),
        seed=int(args.seed),
        intervention=str(args.intervention),
        t0=int(args.t0),
        cap_scale=float(args.cap_scale),
        alpha=float(args.alpha),
        beta=float(args.beta),
        gamma=float(args.gamma),
        demand_mult=float(args.demand_mult),
        demand_start=int(args.demand_start),
        demand_duration=int(args.demand_duration),
    )

    # Persist raw series
    df_control.to_csv(tabdir / "control_timeseries.csv", index=False)
    df_test.to_csv(tabdir / "test_timeseries.csv", index=False)

    # Compute effect on selected metric (post window)
    pre_mask = df_control["t"] < int(args.t0)
    post_mask = df_control["t"] >= int(args.t0)

    metric_col = str(metric_to_use)
    if metric_col not in df_control.columns:
        raise SystemExit(f"Metric '{metric_col}' missing in control output. Columns: {sorted(df_control.columns)}")
    if metric_col not in df_test.columns:
        raise SystemExit(f"Metric '{metric_col}' missing in test output. Columns: {sorted(df_test.columns)}")

    mean_post_control = float(df_control.loc[post_mask, metric_col].mean())
    mean_post_test = float(df_test.loc[post_mask, metric_col].mean())
    effect_size = mean_post_test - mean_post_control

    p_value = float(
        stats.ttest_ind(
            df_control.loc[post_mask, metric_col],
            df_test.loc[post_mask, metric_col],
            equal_var=False,
        ).pvalue
    )

    verdict = "ACCEPT" if (abs(effect_size) >= float(args.sesoi) and p_value <= float(args.alpha_level)) else "INDETERMINATE"

    # Plot V(t) (always)
    plt.figure(figsize=(10, 5))
    plt.plot(df_control["t"], df_control["V"], label="control")
    plt.plot(df_test["t"], df_test["V"], label=f"{args.intervention}")
    plt.axvline(x=int(args.t0), linestyle="--", label="t0")
    plt.xlabel("t")
    plt.ylabel("V")
    plt.title("ORI-C demo: V(t) control vs intervention")
    plt.legend()
    plt.tight_layout()
    v_plot_path = figdir / "v_t_comparison.png"
    plt.savefig(v_plot_path, dpi=150)
    plt.close()

    # Plot selected metric
    plt.figure(figsize=(10, 5))
    plt.plot(df_control["t"], df_control[metric_col], label="control")
    plt.plot(df_test["t"], df_test[metric_col], label=f"{args.intervention}")
    plt.axvline(x=int(args.t0), linestyle="--", label="t0")
    plt.xlabel("t")
    plt.ylabel(metric_col)
    plt.title(f"ORI-C demo: {metric_col}(t) control vs intervention")
    plt.legend()
    plt.tight_layout()
    metric_plot_path = figdir / f"{metric_col.lower()}_t_comparison.png"
    plt.savefig(metric_plot_path, dpi=150)
    plt.close()

    summary = {
        "intervention": str(args.intervention),
        "metric": metric_col,
        "alpha": float(args.alpha_level),
        "sesoi": float(args.sesoi),
        "effect_size": float(effect_size),
        "p_value": float(p_value),
        "verdict": str(verdict),
        "mean_post_control": float(mean_post_control),
        "mean_post_test": float(mean_post_test),
        "t0": int(args.t0),
        "demand_mult": float(args.demand_mult),
        "demand_start": int(args.demand_start),
        "demand_duration": int(args.demand_duration),
        "plots": {
            "v": str(v_plot_path.name),
            "metric": str(metric_plot_path.name),
        },
    }

    pd.DataFrame([summary]).to_csv(tabdir / "summary.csv", index=False)
    with open(outdir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
