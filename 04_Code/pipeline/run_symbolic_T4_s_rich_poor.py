#!/usr/bin/env python3
"""04_Code/pipeline/run_symbolic_T4_s_rich_poor.py

T4: symbolic stock richness test.

Hypothesis
- With identical ORI conditions (same seed, same O/R/I path), a higher initial symbolic stock S0
  yields a higher C(t) trajectory and higher C_end.

Implementation
- For each seed: run two trajectories with the same seed and the same parameters except S0.
- Compare C_end across pairs.

Outputs
- tables/paired_results.csv
- tables/summary.json
- figures/c_end_boxplot.png

CLI keeps historical flags: --n, --t-steps
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

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def _make_dirs(outdir: Path) -> tuple[Path, Path]:
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    return figdir, tabdir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--t-steps", type=int, default=260)

    ap.add_argument("--S-rich", type=float, default=0.70)
    ap.add_argument("--S-poor", type=float, default=0.10)

    ap.add_argument("--sigma-star", type=float, default=1e9, help="High default disables sigma-driven accumulation")
    ap.add_argument("--tau", type=float, default=0.0)
    ap.add_argument("--s-decay", type=float, default=0.002)

    ap.add_argument("--demand-noise", type=float, default=0.0)
    ap.add_argument("--ori-trend", type=float, default=0.0)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    if float(args.tau) > 0.0:
        s_decay = 1.0 / float(args.tau)
    else:
        s_decay = float(args.s_decay)

    rows = []
    for i in range(int(args.n)):
        seed = int(args.seed) + i

        cfg_common = ORICConfig(
            seed=seed,
            n_steps=int(args.t_steps),
            intervention="none",
            intervention_point=int(args.t_steps // 3),
            intervention_duration=0,
            sigma_star=float(args.sigma_star),
            S_decay=float(s_decay),
            demand_noise=float(args.demand_noise),
            ori_trend=float(args.ori_trend),
        )

        df_rich = run_oric(ORICConfig(**{**cfg_common.__dict__, "S0": float(args.S_rich)}))
        df_poor = run_oric(ORICConfig(**{**cfg_common.__dict__, "S0": float(args.S_poor)}))

        rows.append(
            {
                "seed": seed,
                "C_end_rich": float(df_rich["C"].iloc[-1]),
                "C_end_poor": float(df_poor["C"].iloc[-1]),
                "diff_rich_minus_poor": float(df_rich["C"].iloc[-1] - df_poor["C"].iloc[-1]),
            }
        )

    res = pd.DataFrame(rows)
    res.to_csv(tabdir / "paired_results.csv", index=False)

    # Paired test on diff
    diffs = res["diff_rich_minus_poor"].to_numpy(dtype=float)
    tstat, pval = stats.ttest_1samp(diffs, popmean=0.0)

    summary = {
        "n": int(args.n),
        "seed_base": int(args.seed),
        "t_steps": int(args.t_steps),
        "S_rich": float(args.S_rich),
        "S_poor": float(args.S_poor),
        "mean_diff": float(np.mean(diffs)),
        "p_value": float(pval),
    }

    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = {
        "test": "T4_symbolic_S_rich_vs_poor",
        "verdict": "ACCEPT" if float(pval) < 0.01 and float(np.mean(diffs)) > 0 else "INDETERMINATE",
        "mean_diff": float(np.mean(diffs)),
        "p_value": float(pval),
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    # Simple plot
    plt.figure(figsize=(8, 5))
    plt.boxplot([res["C_end_poor"], res["C_end_rich"]], labels=["poor", "rich"])
    plt.ylabel("C_end")
    plt.title("C_end: S0 poor vs rich")
    plt.tight_layout()
    plt.savefig(figdir / "c_end_boxplot.png", dpi=160)
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
