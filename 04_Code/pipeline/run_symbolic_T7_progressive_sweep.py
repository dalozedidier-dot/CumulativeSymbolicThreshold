#!/usr/bin/env python3
"""04_Code/pipeline/run_symbolic_T7_progressive_sweep.py

T7: progressive sweep S0 -> C_end.

Hypothesis
- There exists an effective threshold in initial symbolic stock S0 such that C_end transitions
  from <=0 to >0.

Implementation
- Sweep S0 on a grid, hold everything else constant.
- For each S0, run ORI-C with intervention=none and sigma_star very large (no sigma-driven accumulation).
- Compute C_end and locate the smallest S0 such that C_end > 0.

Outputs
- tables/sweep_results.csv
- tables/summary.json
- figures/c_end_vs_s0.png

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
    ap.add_argument("--n", type=int, default=40, help="Number of S0 points")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--t-steps", type=int, default=260)

    ap.add_argument("--S0-min", type=float, default=0.0)
    ap.add_argument("--S0-max", type=float, default=1.0)

    ap.add_argument("--sigma-star", type=float, default=1e9)
    ap.add_argument("--demand-noise", type=float, default=0.0)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    s0_grid = np.linspace(float(args.S0_min), float(args.S0_max), int(args.n))

    rows = []
    for j, s0 in enumerate(s0_grid):
        # same seed each time for matched ORI; small offset to avoid identical random draws on internal noise
        seed = int(args.seed)
        cfg = ORICConfig(
            seed=seed,
            n_steps=int(args.t_steps),
            intervention="none",
            sigma_star=float(args.sigma_star),
            demand_noise=float(args.demand_noise),
            S0=float(s0),
        )
        df = run_oric(cfg)
        rows.append({"S0": float(s0), "C_end": float(df["C"].iloc[-1])})

    res = pd.DataFrame(rows)
    res.to_csv(tabdir / "sweep_results.csv", index=False)

    # threshold: first S0 where C_end > 0
    thr_s0 = None
    for _, r in res.sort_values("S0").iterrows():
        if float(r["C_end"]) > 0.0:
            thr_s0 = float(r["S0"])
            break

    summary = {
        "n": int(args.n),
        "seed": int(args.seed),
        "t_steps": int(args.t_steps),
        "S0_min": float(args.S0_min),
        "S0_max": float(args.S0_max),
        "threshold_S0": thr_s0,
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = {
        "test": "T7_progressive_S0_sweep",
        "verdict": "ACCEPT" if thr_s0 is not None else "INDETERMINATE",
        "threshold_S0": thr_s0,
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    plt.figure(figsize=(9, 5))
    plt.plot(res["S0"], res["C_end"], marker="o")
    plt.axhline(0.0, linestyle=":")
    if thr_s0 is not None:
        plt.axvline(thr_s0, linestyle="--", label="threshold_S0")
        plt.legend()
    plt.xlabel("S0")
    plt.ylabel("C_end")
    plt.title("Progressive sweep: S0 -> C_end")
    plt.tight_layout()
    plt.savefig(figdir / "c_end_vs_s0.png", dpi=160)
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
