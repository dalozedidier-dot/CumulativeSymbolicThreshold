#!/usr/bin/env python3
"""
04_Code/pipeline/tests_causaux.py

Lightweight causal sanity checks:
- Uses a diff-in-diff style effect on V across control vs intervention.
- Produces one row per intervention with:
  effect_estimate, expected_sign, causal_ok, verdict

Outputs:
- tables/causal_tests_summary.csv
- tables/verdict.json
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

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def _make_dirs(outdir: Path) -> Path:
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)
    (outdir / "figures").mkdir(parents=True, exist_ok=True)
    return tabdir


def _window(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    return df[(df["t"] >= start) & (df["t"] < end)].copy()


def _did_effect(df_c: pd.DataFrame, df_i: pd.DataFrame, t0: int, t1: int) -> float:
    # (post - pre) intervention minus (post - pre) control
    c_pre = float(_window(df_c, 0, t0)["V"].mean())
    c_post = float(_window(df_c, t0, t1)["V"].mean())
    i_pre = float(_window(df_i, 0, t0)["V"].mean())
    i_post = float(_window(df_i, t0, t1)["V"].mean())
    return (i_post - i_pre) - (c_post - c_pre)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--n-steps", type=int, default=200)
    ap.add_argument("--intervention-point", type=int, default=80)
    ap.add_argument("--sesoi-v-rel", type=float, default=0.05)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    tabdir = _make_dirs(outdir)

    interventions = ["symbolic_cut", "demand_shock", "capacity_hit"]

    rows = []
    for iv in interventions:
        cfg_c = ORICConfig(seed=int(args.seed), n_steps=int(args.n_steps), intervention="none", intervention_point=int(args.intervention_point))
        cfg_i = ORICConfig(seed=int(args.seed), n_steps=int(args.n_steps), intervention=iv, intervention_point=int(args.intervention_point))
        df_c = run_oric(cfg_c)
        df_i = run_oric(cfg_i)

        eff = _did_effect(df_c, df_i, int(args.intervention_point), int(args.n_steps))

        # expected negative: intervention should reduce V trajectory
        expected_sign = -1
        ok_sign = (eff < 0.0)

        # SESOI relative to control pre mean for scaling
        c_pre = float(_window(df_c, 0, int(args.intervention_point))["V"].mean())
        sesoi = -float(args.sesoi_v_rel) * abs(c_pre)
        ok_sesoi = (eff <= sesoi)

        causal_ok = bool(ok_sign and ok_sesoi)
        verdict = "ACCEPT" if causal_ok else "INDETERMINATE"

        rows.append(
            {
                "intervention": iv,
                "effect_estimate": eff,
                "expected_sign": expected_sign,
                "sesoi_effect": sesoi,
                "causal_ok": causal_ok,
                "verdict": verdict,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(tabdir / "causal_tests_summary.csv", index=False)

    overall = "ACCEPT" if bool((df["verdict"] == "ACCEPT").all()) else ("INDETERMINATE" if bool((df["verdict"] == "INDETERMINATE").any()) else "REJECT")
    verdict_obj = {"test": "causal_sanity", "verdict": overall, "sesoi_v_rel": float(args.sesoi_v_rel), "interventions": rows}
    (tabdir / "verdict.json").write_text(json.dumps(verdict_obj, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
