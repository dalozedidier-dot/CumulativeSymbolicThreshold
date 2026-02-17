"""
Tests causaux synthétiques sur ORI-C.

Tests:
1) symbolic_cut doit réduire V post intervention vs contrôle.
2) demand_shock doit réduire V post intervention vs contrôle.
3) capacity_hit doit réduire V post intervention vs contrôle.

Produit une table CSV avec les résultats.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

import pandas as pd

# Allow direct execution from repo root: python 04_Code/pipeline/tests_causaux.py
ROOT = Path(__file__).resolve().parents[1]  # 04_Code
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.ori_c_pipeline import ORICConfig, run_oric  # noqa: E402


def _mean_window(df: pd.DataFrame, t_min: int, t_max: int) -> float:
    g = df[(df["t"] >= t_min) & (df["t"] <= t_max)]
    return float(g["V"].mean())


def run_test(intervention: str, seed: int, n_steps: int, intervention_point: int) -> dict:
    cfg_control = ORICConfig(seed=seed, n_steps=n_steps, intervention="none", intervention_point=intervention_point)
    cfg_int = ORICConfig(seed=seed, n_steps=n_steps, intervention=intervention, intervention_point=intervention_point)

    df_control = run_oric(cfg_control)
    df_int = run_oric(cfg_int)

    V_pre = _mean_window(df_int, 0, intervention_point - 1)
    V_post = _mean_window(df_int, intervention_point + 10, min(n_steps - 1, intervention_point + 30))
    V_post_control = _mean_window(df_control, intervention_point + 10, min(n_steps - 1, intervention_point + 30))

    return {
        "intervention": intervention,
        "V_pre": V_pre,
        "V_post": V_post,
        "V_post_control": V_post_control,
        "delta_post_vs_control": V_post - V_post_control,
        "causal_ok": bool(V_post < V_post_control),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-steps", type=int, default=100)
    ap.add_argument("--intervention-point", type=int, default=70)
    args = ap.parse_args()

    outdir = args.outdir
    tables = outdir / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    interventions = ["symbolic_cut", "demand_shock", "capacity_hit"]
    rows = [run_test(itv, args.seed, args.n_steps, args.intervention_point) for itv in interventions]
    df = pd.DataFrame(rows)
    df.to_csv(tables / "table2_tests_causaux.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
