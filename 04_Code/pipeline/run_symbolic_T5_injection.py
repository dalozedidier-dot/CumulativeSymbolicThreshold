#!/usr/bin/env python3
"""04_Code/pipeline/run_symbolic_T5_injection.py

T5: symbolic injection test.

Hypothesis
- A one-step symbolic injection at t0 increases C(t) and C_end relative to a no-injection control.

Implementation
- Paired design: same seed, same parameters, only intervention differs.
- Injection is a one-step pulse via intervention_duration=1.

Outputs
- tables/paired_results.csv
- tables/summary.json
- figures/c_end_boxplot.png

CLI keeps historical flags: --n, --t-steps, --t0
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
    ap.add_argument("--t0", type=int, default=120)

    ap.add_argument("--S0", type=float, default=0.20)
    ap.add_argument("--injection-add", type=float, default=0.25)

    ap.add_argument("--demand-noise", type=float, default=0.0)
    ap.add_argument("--sigma-star", type=float, default=1e9)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    rows = []
    for i in range(int(args.n)):
        seed = int(args.seed) + i

        cfg_common = ORICConfig(
            seed=seed,
            n_steps=int(args.t_steps),
            intervention_point=int(args.t0),
            intervention_duration=1,
            demand_noise=float(args.demand_noise),
            sigma_star=float(args.sigma_star),
            S0=float(args.S0),
        )

        df_ctrl = run_oric(ORICConfig(**{**cfg_common.__dict__, "intervention": "none"}))
        df_inj = run_oric(
            ORICConfig(
                **{
                    **cfg_common.__dict__,
                    "intervention": "symbolic_injection",
                    "symbolic_injection_add": float(args.injection_add),
                }
            )
        )

        rows.append(
            {
                "seed": seed,
                "C_end_control": float(df_ctrl["C"].iloc[-1]),
                "C_end_injection": float(df_inj["C"].iloc[-1]),
                "diff_injection_minus_control": float(df_inj["C"].iloc[-1] - df_ctrl["C"].iloc[-1]),
            }
        )

    res = pd.DataFrame(rows)
    res.to_csv(tabdir / "paired_results.csv", index=False)

    diffs = res["diff_injection_minus_control"].to_numpy(dtype=float)
    tstat, pval = stats.ttest_1samp(diffs, popmean=0.0)

    summary = {
        "n": int(args.n),
        "seed_base": int(args.seed),
        "t_steps": int(args.t_steps),
        "t0": int(args.t0),
        "S0": float(args.S0),
        "injection_add": float(args.injection_add),
        "mean_diff": float(np.mean(diffs)),
        "p_value": float(pval),
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = {
        "test": "T5_symbolic_injection",
        "verdict": "ACCEPT" if float(pval) < 0.01 and float(np.mean(diffs)) > 0 else "INDETERMINATE",
        "mean_diff": float(np.mean(diffs)),
        "p_value": float(pval),
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    plt.figure(figsize=(8, 5))
    plt.boxplot([res["C_end_control"], res["C_end_injection"]], labels=["control", "injection"])
    plt.ylabel("C_end")
    plt.title("C_end: control vs injection")
    plt.tight_layout()
    plt.savefig(figdir / "c_end_boxplot.png", dpi=160)
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
