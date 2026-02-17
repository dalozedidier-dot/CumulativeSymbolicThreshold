#!/usr/bin/env python3
"""
04_Code/pipeline/run_ori_c_demo.py

Runs a simple ORI-C demonstration:
- control (no intervention)
- intervention (one exogenous intervention)
Writes:
- tables/timeseries_control.csv
- tables/timeseries_intervention.csv
- tables/summary.csv
- tables/verdict.json
- figures/v_compare.png
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

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def _make_dirs(outdir: Path) -> tuple[Path, Path]:
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    return figdir, tabdir


def _window(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    return df[(df["t"] >= start) & (df["t"] < end)].copy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--n-steps", type=int, default=200)
    ap.add_argument(
        "--intervention",
        default="symbolic_cut",
        choices=["demand_shock", "capacity_hit", "symbolic_cut", "symbolic_injection", "symbolic_cut_then_inject"],
    )
    ap.add_argument("--intervention-point", type=int, default=80)
    ap.add_argument("--reinjection-point", type=int, default=120)
    ap.add_argument("--sesoi-v-rel", type=float, default=0.10)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    cfg_control = ORICConfig(seed=int(args.seed), n_steps=int(args.n_steps), intervention="none", intervention_point=int(args.intervention_point))
    cfg_interv = ORICConfig(
        seed=int(args.seed),
        n_steps=int(args.n_steps),
        intervention=str(args.intervention),
        intervention_point=int(args.intervention_point),
        reinjection_point=int(args.reinjection_point),
    )

    df_c = run_oric(cfg_control)
    df_i = run_oric(cfg_interv)

    df_c.to_csv(tabdir / "timeseries_control.csv", index=False)
    df_i.to_csv(tabdir / "timeseries_intervention.csv", index=False)

    pre = (0, int(args.intervention_point))
    post = (int(args.intervention_point), int(args.n_steps))

    c_pre = float(_window(df_c, *pre)["V"].mean())
    c_post = float(_window(df_c, *post)["V"].mean())
    i_pre = float(_window(df_i, *pre)["V"].mean())
    i_post = float(_window(df_i, *post)["V"].mean())

    effect = i_post - c_post  # negative means intervention harms V

    summary = pd.DataFrame(
        [
            {"condition": "control", "V_mean_pre": c_pre, "V_mean_post": c_post},
            {"condition": "intervention", "intervention": str(args.intervention), "V_mean_pre": i_pre, "V_mean_post": i_post},
        ]
    )
    summary.to_csv(tabdir / "summary.csv", index=False)

    # Verdict: accept if post drop is at least SESOI relative to control post
    sesoi = -float(args.sesoi_v_rel) * abs(c_post)
    verdict = "ACCEPT" if (effect <= sesoi) else "INDETERMINATE"

    verdict_obj = {
        "test": "ori_c_demo",
        "intervention": str(args.intervention),
        "sesoi_v_rel": float(args.sesoi_v_rel),
        "control_V_post": c_post,
        "intervention_V_post": i_post,
        "effect": effect,
        "sesoi_effect": sesoi,
        "verdict": verdict,
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict_obj, indent=2), encoding="utf-8")

    # Figure
    plt.figure(figsize=(10, 5))
    plt.plot(df_c["t"], df_c["V"], label="control V(t)")
    plt.plot(df_i["t"], df_i["V"], label=f"intervention V(t): {args.intervention}")
    plt.axvline(int(args.intervention_point), linestyle="--", label="intervention point")
    plt.xlabel("t")
    plt.ylabel("V")
    plt.title("ORI-C demo: V(t) control vs intervention")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figdir / "v_compare.png", dpi=160)
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
