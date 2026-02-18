#!/usr/bin/env python3
"""04_Code/pipeline/run_falsification_demo.py

Falsification and counterfactual demos.

Purpose
- Provide explicit cases that should falsify the hypothesis "C(t) > 0 persists and is attributable to S(t)".
- Produce artifacts that are easy to post (timeseries + figures + causal report).

Scenarios (each produces control vs test)
1) baseline_positive: demand shock with symbolic accumulation enabled
2) no_S: demand shock but sigma_to_S_alpha = 0 (no symbolic accumulation)
3) cut_channel: symbolic_cut to near-zero S with sigma_to_S_alpha = 0 and higher decay
4) capacity_only: capacity hit but weak symbolic coupling (optional stress without S)

Outputs
- <outdir>/<scenario>/run_0001/... (same structure as run_ori_c_demo)
- <outdir>/<scenario>/tables/summary_all.csv
- Optional causal report per run via tests_causaux.py

Example
python 04_Code/pipeline/run_falsification_demo.py \
  --outdir 05_Results/falsification \
  --n-runs 8 --seed-base 2000 --n-steps 2600 --t0 900 \
  --sigma-star 120 --tau 700 --run-causal
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
import subprocess

import pandas as pd

from pipeline.ori_c_pipeline import ORICConfig
from pipeline.run_ori_c_demo import run_one


def _run_causal(run_dir: Path, alpha: float, c_min: float, lags: str, pdf: bool) -> None:
    cmd = [
        sys.executable,
        str(_CODE_DIR / "pipeline" / "tests_causaux.py"),
        "--run-dir",
        str(run_dir),
        "--alpha",
        str(alpha),
        "--c-mean-post-min",
        str(c_min),
        "--lags",
        str(lags),
        "--n-steps-min",
        "2000",
    ]
    if pdf:
        cmd.append("--pdf")
    subprocess.run(cmd, check=False)


def _scenario_configs(base: ORICConfig, scenario: str) -> tuple[ORICConfig, ORICConfig]:
    # Control always baseline positive
    cfg_control = ORICConfig(**{**asdict(base), "intervention": "none"})

    if scenario == "baseline_positive":
        cfg_test = ORICConfig(**{**asdict(base), "intervention": "demand_shock"})
        return cfg_control, cfg_test

    if scenario == "no_S":
        cfg_test = ORICConfig(
            **{
                **asdict(base),
                "intervention": "demand_shock",
                "sigma_to_S_alpha": 0.0,
            }
        )
        return cfg_control, cfg_test

    if scenario == "cut_channel":
        cfg_test = ORICConfig(
            **{
                **asdict(base),
                "intervention": "symbolic_cut",
                "symbolic_cut_factor": 0.0,
                "sigma_to_S_alpha": 0.0,
                "S_decay": max(float(base.S_decay), 0.01),
            }
        )
        return cfg_control, cfg_test

    if scenario == "capacity_only":
        cfg_test = ORICConfig(
            **{
                **asdict(base),
                "intervention": "capacity_hit",
                "sigma_to_S_alpha": 0.0,
            }
        )
        return cfg_control, cfg_test

    raise ValueError(f"Unknown scenario: {scenario}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)

    ap.add_argument("--n-runs", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=2000)

    ap.add_argument("--n-steps", type=int, default=2600)
    ap.add_argument("--t0", type=int, default=900)

    ap.add_argument("--intervention-duration", type=int, default=300)
    ap.add_argument("--sigma-star", type=float, default=120.0)
    ap.add_argument("--tau", type=float, default=700.0)

    ap.add_argument("--demand-noise", type=float, default=0.05)
    ap.add_argument("--ori-trend", type=float, default=0.0)

    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)

    ap.add_argument("--delta", type=int, default=250)
    ap.add_argument("--T", type=int, default=600)

    ap.add_argument("--run-causal", action="store_true")
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--c-mean-post-min", type=float, default=0.1)
    ap.add_argument("--lags", type=str, default="1-10")
    ap.add_argument("--pdf", action="store_true")

    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    s_decay = 1.0 / float(args.tau) if float(args.tau) > 0.0 else 0.002

    base = ORICConfig(
        seed=int(args.seed_base),
        n_steps=int(args.n_steps),
        intervention_point=int(args.t0),
        intervention_duration=int(args.intervention_duration),
        sigma_star=float(args.sigma_star),
        S_decay=float(s_decay),
        demand_noise=float(args.demand_noise),
        ori_trend=float(args.ori_trend),
        k=float(args.k),
        m=int(args.m),
        baseline_n=int(args.baseline_n),
    )

    scenarios = ["baseline_positive", "no_S", "cut_channel", "capacity_only"]

    for sc in scenarios:
        sc_dir = outdir / sc
        sc_dir.mkdir(parents=True, exist_ok=True)
        summaries = []

        for i in range(int(args.n_runs)):
            seed = int(args.seed_base) + i
            run_dir = sc_dir / f"run_{i+1:04d}"

            cfg_control, cfg_test = _scenario_configs(base, sc)
            cfg_control = ORICConfig(**{**asdict(cfg_control), "seed": seed})
            cfg_test = ORICConfig(**{**asdict(cfg_test), "seed": seed})

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

            # Flatten key params
            summaries.append(
                {
                    "scenario": sc,
                    "seed": seed,
                    "threshold_hit_t": summ.get("threshold_hit_t"),
                    "C_mean_post": summ.get("C_mean_post"),
                    "C_positive_frac_post": summ.get("C_positive_frac_post"),
                    "effect_C_post_mean": summ.get("effect_C_post_mean"),
                    "p_value_C_post_mean": summ.get("p_value_C_post_mean"),
                    "run_dir": str(run_dir.relative_to(sc_dir)),
                }
            )

            if bool(args.run_causal):
                _run_causal(run_dir, alpha=float(args.alpha), c_min=float(args.c_mean_post_min), lags=str(args.lags), pdf=bool(args.pdf))

        tabdir = sc_dir / "tables"
        tabdir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(summaries)
        df.to_csv(tabdir / "summary_all.csv", index=False)

    print(f"Wrote: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
