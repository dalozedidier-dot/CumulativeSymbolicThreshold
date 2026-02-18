#!/usr/bin/env python3
"""04_Code/pipeline/run_threshold_validation_suite.py

Empirical validation suite for the cumulative threshold condition.

This is a parametric wrapper around the ORI-C simulator.
It produces multiple runs under multiple parameter settings to show that:
- C(t) transitions from ~0 to persistently > 0 under stress
- The detection remains stable across Sigma*, tau, and noise or trend variants

Outputs
- <outdir>/<case_id>/run_0001/... (same structure as run_ori_c_demo)
- <outdir>/tables/suite_summary.csv
- <outdir>/tables/suite_manifest.json

Example
python 04_Code/pipeline/run_threshold_validation_suite.py \
  --outdir 05_Results/threshold_validation/suite \
  --replicates 2 --seed-base 1000 --n-steps 2600 --t0 900 \
  --intervention demand_shock --intervention-duration 250 \
  --sigma-stars 0,120 --taus 400,800 --demand-noises 0.03,0.06 --ori-trends 0,0.0005
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import argparse
import json

import pandas as pd

from pipeline.ori_c_pipeline import ORICConfig
from pipeline.run_ori_c_demo import run_one


def _parse_floats(s: str) -> list[float]:
    s = str(s).strip()
    if not s:
        return []
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def _case_id(sigma_star: float, tau: float, demand_noise: float, ori_trend: float) -> str:
    return f"sigstar_{sigma_star:.3g}__tau_{tau:.3g}__dn_{demand_noise:.3g}__trend_{ori_trend:.3g}".replace(".", "p")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)

    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=1000)

    ap.add_argument("--n-steps", type=int, default=2600)
    ap.add_argument("--t0", type=int, default=900)

    ap.add_argument(
        "--intervention",
        default="demand_shock",
        choices=[
            "none",
            "demand_shock",
            "capacity_hit",
            "symbolic_cut",
            "symbolic_injection",
            "symbolic_cut_then_inject",
        ],
    )
    ap.add_argument("--intervention-duration", type=int, default=250)

    ap.add_argument("--sigma-stars", type=str, default="0,120")
    ap.add_argument("--taus", type=str, default="400,800")
    ap.add_argument("--demand-noises", type=str, default="0.03")
    ap.add_argument("--ori-trends", type=str, default="0,0.0005")

    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)

    ap.add_argument("--delta", type=int, default=250)
    ap.add_argument("--T", type=int, default=600)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "tables").mkdir(parents=True, exist_ok=True)

    sigma_stars = _parse_floats(args.sigma_stars)
    taus = _parse_floats(args.taus)
    demand_noises = _parse_floats(args.demand_noises)
    ori_trends = _parse_floats(args.ori_trends)

    if not sigma_stars:
        sigma_stars = [0.0]
    if not taus:
        taus = [700.0]
    if not demand_noises:
        demand_noises = [0.03]
    if not ori_trends:
        ori_trends = [0.0]

    rows = []
    seed = int(args.seed_base)

    for sigstar in sigma_stars:
        for tau in taus:
            s_decay = 1.0 / float(tau) if float(tau) > 0.0 else 0.002
            for dn in demand_noises:
                for tr in ori_trends:
                    case = _case_id(sigstar, tau, dn, tr)
                    case_dir = outdir / case
                    case_dir.mkdir(parents=True, exist_ok=True)

                    base = ORICConfig(
                        seed=seed,
                        n_steps=int(args.n_steps),
                        intervention_point=int(args.t0),
                        intervention_duration=int(args.intervention_duration),
                        intervention=str(args.intervention),
                        sigma_star=float(sigstar),
                        S_decay=float(s_decay),
                        demand_noise=float(dn),
                        ori_trend=float(tr),
                        k=float(args.k),
                        m=int(args.m),
                        baseline_n=int(args.baseline_n),
                    )

                    cfg_control_tmpl = ORICConfig(**{**asdict(base), "intervention": "none"})
                    cfg_test_tmpl = base

                    for r in range(int(args.replicates)):
                        run_dir = case_dir / f"run_{r+1:04d}"
                        cfg_control = ORICConfig(**{**asdict(cfg_control_tmpl), "seed": seed})
                        cfg_test = ORICConfig(**{**asdict(cfg_test_tmpl), "seed": seed})

                        summ = run_one(
                            outdir=run_dir,
                            seed=seed,
                            cfg_control=cfg_control,
                            cfg_test=cfg_test,
                            delta=int(args.delta),
                            T=int(args.T),
                            csd_window=80,
                            write_csd=True,
                        )

                        rows.append(
                            {
                                "case": case,
                                "seed": seed,
                                "sigma_star": float(sigstar),
                                "tau": float(tau),
                                "demand_noise": float(dn),
                                "ori_trend": float(tr),
                                "intervention": str(args.intervention),
                                "threshold_hit_t": summ.get("threshold_hit_t"),
                                "C_mean_post": summ.get("C_mean_post"),
                                "C_positive_frac_post": summ.get("C_positive_frac_post"),
                                "effect_C_post_mean": summ.get("effect_C_post_mean"),
                                "p_value_C_post_mean": summ.get("p_value_C_post_mean"),
                                "run_dir": str(run_dir.relative_to(outdir)),
                            }
                        )

                        seed += 1

    df = pd.DataFrame(rows)
    df.to_csv(outdir / "tables" / "suite_summary.csv", index=False)

    manifest = {
        "outdir": str(outdir),
        "replicates": int(args.replicates),
        "seed_base": int(args.seed_base),
        "n_steps": int(args.n_steps),
        "t0": int(args.t0),
        "intervention": str(args.intervention),
        "intervention_duration": int(args.intervention_duration),
        "sigma_stars": sigma_stars,
        "taus": taus,
        "demand_noises": demand_noises,
        "ori_trends": ori_trends,
        "k": float(args.k),
        "m": int(args.m),
        "baseline_n": int(args.baseline_n),
    }

    (outdir / "tables" / "suite_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote: {outdir / 'tables' / 'suite_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
