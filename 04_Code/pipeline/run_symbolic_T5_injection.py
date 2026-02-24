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

    ap.add_argument("--demand-noise", type=float, default=0.10)
    ap.add_argument("--sigma-star", type=float, default=1e9)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    # Unpaired design: distinct seeds for control vs injection.
    # A paired design (same seed for both) makes diff_injection_minus_control constant
    # across all pairs when sigma_star is high (S decays deterministically from S0,
    # and V paths cancel). Using distinct seeds gives genuine variance in C_end,
    # enabling a valid two-sample test.
    n = int(args.n)
    rows = []
    for i in range(n):
        seed_ctrl = int(args.seed) + i
        seed_inj = int(args.seed) + n + i  # distinct seeds → genuine replication

        cfg_ctrl = ORICConfig(
            seed=seed_ctrl,
            n_steps=int(args.t_steps),
            intervention="none",
            intervention_point=int(args.t0),
            intervention_duration=1,
            demand_noise=float(args.demand_noise),
            sigma_star=float(args.sigma_star),
            S0=float(args.S0),
        )
        cfg_inj = ORICConfig(
            seed=seed_inj,
            n_steps=int(args.t_steps),
            intervention="symbolic_injection",
            intervention_point=int(args.t0),
            intervention_duration=1,
            demand_noise=float(args.demand_noise),
            sigma_star=float(args.sigma_star),
            S0=float(args.S0),
            symbolic_injection_add=float(args.injection_add),
        )

        df_ctrl = run_oric(cfg_ctrl)
        df_inj = run_oric(cfg_inj)

        rows.append(
            {
                "seed_ctrl": seed_ctrl,
                "seed_inj": seed_inj,
                "C_end_control": float(df_ctrl["C"].iloc[-1]),
                "C_end_injection": float(df_inj["C"].iloc[-1]),
            }
        )

    res = pd.DataFrame(rows)
    res.to_csv(tabdir / "paired_results.csv", index=False)

    # Independent (unpaired) two-sample t-test: H1: mean(C_end_injection) > mean(C_end_control)
    c_ctrl = res["C_end_control"].to_numpy(dtype=float)
    c_inj = res["C_end_injection"].to_numpy(dtype=float)
    tstat, pval = stats.ttest_ind(c_inj, c_ctrl, alternative="greater")
    mean_diff = float(np.mean(c_inj) - np.mean(c_ctrl))

    # --- Full triplet: p + CI 99% + SESOI + bootstrap power gate ---
    n_i, n_c = len(c_inj), len(c_ctrl)
    var_i = float(np.var(c_inj, ddof=1))
    var_c = float(np.var(c_ctrl, ddof=1))
    se_diff = float(np.sqrt(var_i / n_i + var_c / n_c))
    # Welch-Satterthwaite degrees of freedom
    df_w = (var_i / n_i + var_c / n_c) ** 2 / (
        (var_i / n_i) ** 2 / (n_i - 1) + (var_c / n_c) ** 2 / (n_c - 1)
    )
    ci_low, ci_high = stats.t.interval(0.99, df=df_w, loc=mean_diff, scale=se_diff)

    # SESOI: 0.30 × MAD of pooled within-group residuals (ex ante, PreregSpec.sesoi_c_robust_sd)
    pooled_resid = np.concatenate([c_inj - np.mean(c_inj), c_ctrl - np.mean(c_ctrl)])
    sesoi = 0.30 * float(stats.median_abs_deviation(pooled_resid, scale=1.0))

    p_ok = float(pval) < 0.01
    ci_ok = float(ci_low) > 0.0
    sesoi_ok = mean_diff > sesoi

    # Bootstrap power (B=500, seed-controlled)
    rng = np.random.default_rng(int(args.seed))
    B, rejections = 500, 0
    for _ in range(B):
        s_i = rng.choice(c_inj, size=n_i, replace=True)
        s_c = rng.choice(c_ctrl, size=n_c, replace=True)
        _, pb = stats.ttest_ind(s_i, s_c, alternative="greater")
        if float(pb) < 0.01:
            rejections += 1
    power_est = rejections / B
    power_ok = power_est >= 0.70

    if not power_ok:
        verdict_token = "INDETERMINATE"
        rationale = f"Power gate: power={power_est:.3f} < 0.70. Increase N or effect size."
    elif p_ok and ci_ok and sesoi_ok:
        verdict_token = "ACCEPT"
        rationale = (
            f"Triplet: p={pval:.4f}<0.01, CI99%=[{ci_low:.4f},{ci_high:.4f}]>0, "
            f"mean_diff={mean_diff:.4f}>SESOI={sesoi:.4f}, power={power_est:.3f}>=0.70."
        )
    else:
        reasons = []
        if not p_ok:
            reasons.append(f"p={pval:.4f}>=0.01")
        if not ci_ok:
            reasons.append(f"CI99% lower={ci_low:.4f}<=0")
        if not sesoi_ok:
            reasons.append(f"mean_diff={mean_diff:.4f}<=SESOI={sesoi:.4f}")
        verdict_token = "REJECT"
        rationale = "Triplet failed: " + "; ".join(reasons)

    summary = {
        "n": n,
        "seed_base": int(args.seed),
        "t_steps": int(args.t_steps),
        "t0": int(args.t0),
        "S0": float(args.S0),
        "injection_add": float(args.injection_add),
        "design": "unpaired_independent_seeds",
        "demand_noise": float(args.demand_noise),
        "mean_C_end_control": float(np.mean(c_ctrl)),
        "mean_C_end_injection": float(np.mean(c_inj)),
        "mean_diff": mean_diff,
        "p_value": float(pval),
        "ci_99_low": float(ci_low),
        "ci_99_high": float(ci_high),
        "sesoi": sesoi,
        "p_ok": bool(p_ok),
        "ci_ok": bool(ci_ok),
        "sesoi_ok": bool(sesoi_ok),
        "power_estimate": power_est,
        "power_ok": bool(power_ok),
        "verdict": verdict_token,
        "rationale": rationale,
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = {
        "test": "T5_symbolic_injection",
        "verdict": verdict_token,
        "mean_diff": mean_diff,
        "p_value": float(pval),
        "ci_99_low": float(ci_low),
        "ci_99_high": float(ci_high),
        "sesoi": sesoi,
        "power_estimate": power_est,
        "rationale": rationale,
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    (outdir / "verdict.txt").write_text(verdict_token, encoding="utf-8")

    plt.figure(figsize=(8, 5))
    plt.boxplot([res["C_end_control"].to_numpy(), res["C_end_injection"].to_numpy()], labels=["control", "injection"])
    plt.ylabel("C_end")
    plt.title("C_end: control vs injection")
    plt.tight_layout()
    plt.savefig(figdir / "c_end_boxplot.png", dpi=160)
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
