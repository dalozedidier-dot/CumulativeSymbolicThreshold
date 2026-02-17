#!/usr/bin/env python3
"""
04_Code/pipeline/run_reinjection_demo.py

Test 8 (reinjection) demo:
- Apply a symbolic cut at intervention_point
- Apply a symbolic reinjection at reinjection_point
- Evaluate post-reinjection recovery via slope of C(t) over a fixed window
  using scipy.stats.linregress.

Outputs:
- tables/reinjection_timeseries.csv
- tables/summary.json
- tables/verdict.json
- figures/c_t_reinjection.png
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
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def _make_dirs(outdir: Path) -> tuple[Path, Path]:
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    return figdir, tabdir


def _plot(df: pd.DataFrame, cfg: ORICConfig, outpath: Path) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(df["t"], df["C"], label="C(t)")
    plt.axvline(cfg.intervention_point, linestyle="--", label="cut point")
    plt.axvline(cfg.reinjection_point, linestyle="--", label="reinjection point")
    plt.xlabel("t")
    plt.ylabel("C")
    plt.title("Reinjection demo: C(t) trajectory")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--n-steps", type=int, default=220)
    ap.add_argument("--intervention-point", type=int, default=80)
    ap.add_argument("--reinjection-point", type=int, default=130)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--sesoi-slope", type=float, default=0.0, help="Minimal slope for ACCEPT")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    cfg = ORICConfig(
        seed=int(args.seed),
        n_steps=int(args.n_steps),
        intervention="symbolic_cut_then_inject",
        intervention_point=int(args.intervention_point),
        reinjection_point=int(args.reinjection_point),
    )
    df = run_oric(cfg)
    df.to_csv(tabdir / "reinjection_timeseries.csv", index=False)

    # Post-reinjection recovery slope on C(t)
    post = df[df["t"] >= cfg.reinjection_point].copy()
    post = post.iloc[: max(2, int(args.window))].copy()
    res = linregress(post["t"].to_numpy(), post["C"].to_numpy())

    slope = float(res.slope)
    p_slope = float(res.pvalue)

    verdict = "ACCEPT" if (slope > float(args.sesoi_slope) and p_slope <= float(args.alpha)) else "INDETERMINATE"

    summary = {
        "seed": int(args.seed),
        "n_steps": int(args.n_steps),
        "intervention_point": int(cfg.intervention_point),
        "reinjection_point": int(cfg.reinjection_point),
        "window": int(args.window),
        "slope": slope,
        "p_slope": p_slope,
        "alpha": float(args.alpha),
        "sesoi_slope": float(args.sesoi_slope),
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict_obj = {
        "test": "reinjection_slope",
        "verdict": verdict,
        "slope": slope,
        "p_slope": p_slope,
        "alpha": float(args.alpha),
        "sesoi_slope": float(args.sesoi_slope),
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict_obj, indent=2), encoding="utf-8")

    _plot(df, cfg, figdir / "c_t_reinjection.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
