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

import numpy as np
from scipy import stats as scipy_stats

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


def _run_single_reinjection(
    seed: int,
    n_steps: int,
    intervention_point: int,
    reinjection_point: int,
    window: int,
) -> tuple[float, float]:
    """Run one reinjection trajectory, return (slope, p_slope)."""
    cfg = ORICConfig(
        seed=seed,
        n_steps=n_steps,
        intervention="symbolic_cut_then_inject",
        intervention_point=intervention_point,
        reinjection_point=reinjection_point,
    )
    df = run_oric(cfg)
    post = df[df["t"] >= cfg.reinjection_point].copy()
    post = post.iloc[: max(2, window)].copy()
    res = linregress(post["t"].to_numpy(), post["C"].to_numpy())
    return float(res.slope), float(res.pvalue)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--n-runs", type=int, default=1,
                    help="Number of independent replications (N>=50 for full_statistical conformance)")
    ap.add_argument("--n-steps", type=int, default=220)
    ap.add_argument("--intervention-point", type=int, default=80)
    ap.add_argument("--reinjection-point", type=int, default=130)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--sesoi-slope", type=float, default=0.0, help="Minimal slope for ACCEPT")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    n_runs = int(args.n_runs)

    if n_runs <= 1:
        # Single-run path (smoke / illustrative)
        slope, p_slope = _run_single_reinjection(
            seed=int(args.seed),
            n_steps=int(args.n_steps),
            intervention_point=int(args.intervention_point),
            reinjection_point=int(args.reinjection_point),
            window=int(args.window),
        )
        verdict = "ACCEPT" if (slope > float(args.sesoi_slope) and p_slope <= float(args.alpha)) else "INDETERMINATE"

        cfg_plot = ORICConfig(
            seed=int(args.seed),
            n_steps=int(args.n_steps),
            intervention="symbolic_cut_then_inject",
            intervention_point=int(args.intervention_point),
            reinjection_point=int(args.reinjection_point),
        )
        df_plot = run_oric(cfg_plot)
        df_plot.to_csv(tabdir / "reinjection_timeseries.csv", index=False)
        _plot(df_plot, cfg_plot, figdir / "c_t_reinjection.png")

        summary = {
            "n_runs": 1,
            "seed": int(args.seed),
            "n_steps": int(args.n_steps),
            "intervention_point": int(args.intervention_point),
            "reinjection_point": int(args.reinjection_point),
            "window": int(args.window),
            "slope": slope,
            "p_slope": p_slope,
            "alpha": float(args.alpha),
            "sesoi_slope": float(args.sesoi_slope),
            "verdict": verdict,
        }
        (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        verdict_obj = {
            "test": "reinjection_slope",
            "n_runs": 1,
            "verdict": verdict,
            "slope": slope,
            "p_slope": p_slope,
            "alpha": float(args.alpha),
            "sesoi_slope": float(args.sesoi_slope),
        }
        (tabdir / "verdict.json").write_text(json.dumps(verdict_obj, indent=2), encoding="utf-8")
        (outdir / "verdict.txt").write_text(verdict, encoding="utf-8")

    else:
        # Multi-run path: between-run statistical aggregation (triplet: p + CI99% + SESOI + power)
        slopes: list[float] = []
        for i in range(n_runs):
            seed_i = int(args.seed) + i
            slope_i, _ = _run_single_reinjection(
                seed=seed_i,
                n_steps=int(args.n_steps),
                intervention_point=int(args.intervention_point),
                reinjection_point=int(args.reinjection_point),
                window=int(args.window),
            )
            slopes.append(slope_i)

        slopes_arr = np.array(slopes, dtype=float)
        n_valid = len(slopes_arr)
        mean_slope = float(np.mean(slopes_arr))
        mad_slope = float(scipy_stats.median_abs_deviation(slopes_arr, scale=1.0))
        std_slope = float(np.std(slopes_arr, ddof=1))
        se_slope = std_slope / np.sqrt(n_valid)

        t_res = scipy_stats.ttest_1samp(slopes_arr, 0.0)
        t_stat = float(t_res.statistic)
        p_two = float(t_res.pvalue)
        # H1: mean slope > 0 (recovery = positive slope post-reinjection)
        p_one = p_two / 2.0 if t_stat > 0 else 1.0 - p_two / 2.0

        ci_low, ci_high = (float("nan"), float("nan"))
        if se_slope > 0:
            ci_low, ci_high = scipy_stats.t.interval(0.99, df=n_valid - 1, loc=mean_slope, scale=se_slope)

        sesoi = float(args.sesoi_slope)  # SESOI on slope (ex ante, default 0)
        p_ok = p_one < float(args.alpha)
        ci_ok = float(ci_low) > sesoi if np.isfinite(ci_low) else False
        sesoi_ok = mean_slope > sesoi

        # Bootstrap power (B=500)
        rng = np.random.default_rng(int(args.seed))
        rejections = 0
        B = 500
        for _ in range(B):
            sample = rng.choice(slopes_arr, size=n_valid, replace=True)
            t_b, p_b = scipy_stats.ttest_1samp(sample, 0.0)
            t_b, p_b = float(t_b), float(p_b)
            p_use = p_b / 2.0 if t_b > 0 else 1.0 - p_b / 2.0
            if p_use < float(args.alpha):
                rejections += 1
        power_est = rejections / B
        power_ok = power_est >= 0.70

        if not power_ok:
            verdict = "INDETERMINATE"
            rationale = f"Power gate: estimated_power={power_est:.3f} < 0.70. Increase N or effect size."
        elif p_ok and ci_ok and sesoi_ok:
            verdict = "ACCEPT"
            rationale = (
                f"Triplet satisfied: p_one={p_one:.4f}<{args.alpha}, "
                f"CI99%=[{ci_low:.4f},{ci_high:.4f}]>{sesoi}, "
                f"mean_slope={mean_slope:.4f}>SESOI={sesoi}."
            )
        else:
            reasons = []
            if not p_ok:
                reasons.append(f"p_one={p_one:.4f}>={args.alpha}")
            if not ci_ok:
                reasons.append(f"CI99% lower={ci_low:.4f} not >{sesoi}")
            if not sesoi_ok:
                reasons.append(f"mean_slope={mean_slope:.4f}<=SESOI={sesoi}")
            verdict = "REJECT"
            rationale = "Triplet failed: " + "; ".join(reasons)

        # Plot first trajectory for illustration
        cfg_plot = ORICConfig(
            seed=int(args.seed),
            n_steps=int(args.n_steps),
            intervention="symbolic_cut_then_inject",
            intervention_point=int(args.intervention_point),
            reinjection_point=int(args.reinjection_point),
        )
        df_plot = run_oric(cfg_plot)
        df_plot.to_csv(tabdir / "reinjection_timeseries.csv", index=False)
        _plot(df_plot, cfg_plot, figdir / "c_t_reinjection.png")

        summary = {
            "n_runs": n_valid,
            "seed_base": int(args.seed),
            "intervention_point": int(args.intervention_point),
            "reinjection_point": int(args.reinjection_point),
            "window": int(args.window),
            "mean_slope": mean_slope,
            "mad_slope": mad_slope,
            "std_slope": std_slope,
            "se_slope": se_slope,
            "t_stat": t_stat,
            "p_one_sided": p_one,
            "ci_99_low": float(ci_low),
            "ci_99_high": float(ci_high),
            "sesoi_slope": sesoi,
            "p_ok": bool(p_ok),
            "ci_ok": bool(ci_ok),
            "sesoi_ok": bool(sesoi_ok),
            "power_estimate": power_est,
            "power_ok": bool(power_ok),
            "verdict": verdict,
            "rationale": rationale,
        }
        (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (tabdir / "verdict.json").write_text(
            json.dumps({"test": "reinjection_slope_multi", "verdict": verdict, "rationale": rationale}, indent=2),
            encoding="utf-8",
        )
        (outdir / "verdict.txt").write_text(verdict, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
