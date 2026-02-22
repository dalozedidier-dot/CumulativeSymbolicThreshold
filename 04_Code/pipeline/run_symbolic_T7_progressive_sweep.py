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
from scipy import stats as scipy_stats

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

    # --- Bootstrap triplet for T7 ---
    # Falsification (H0): C_end is strictly linear in S0 (no tipping point).
    # H1: a threshold S0* exists strictly in the interior of [S0_min, S0_max].
    #
    # Bootstrap: resample the N (S0_i, C_end_i) grid points with replacement,
    # detect threshold_S0 in each bootstrap → CI 99% + power estimate.
    #   p_hat     = fraction of bootstraps NOT detecting a threshold (proxy for H0 p-value)
    #   power_est = fraction detecting a threshold (≥ 0.70 required)
    #   ci_99     = [0.5th, 99.5th] percentile of detected threshold_S0 values
    #   SESOI     = threshold must be in interior (not within 10% of S0_min/max edges)
    s0_arr = res["S0"].to_numpy(dtype=float)
    c_end_arr = res["C_end"].to_numpy(dtype=float)
    s0_min = float(args.S0_min)
    s0_max = float(args.S0_max)
    margin = 0.10 * (s0_max - s0_min)

    rng = np.random.default_rng(int(args.seed))
    B = 500
    boot_thresholds: list[float | None] = []
    for _ in range(B):
        idx = rng.integers(0, len(s0_arr), size=len(s0_arr))
        s0_b = s0_arr[idx]
        c_b = c_end_arr[idx]
        sorted_order = np.argsort(s0_b)
        thr_b: float | None = None
        for k in sorted_order:
            if float(c_b[k]) > 0.0:
                thr_b = float(s0_b[k])
                break
        boot_thresholds.append(thr_b)

    detected = [t for t in boot_thresholds if t is not None]
    detection_count = len(detected)
    p_hat = 1.0 - detection_count / B     # fraction NOT detecting (H0 proxy)
    power_est = detection_count / B       # fraction detecting (H1 support)

    if len(detected) >= 2:
        ci_low = float(np.percentile(detected, 0.5))
        ci_high = float(np.percentile(detected, 99.5))
    else:
        ci_low = ci_high = float("nan")

    # SESOI: threshold must be strictly in interior (not at edges ± 10% margin)
    sesoi_ok = (
        thr_s0 is not None
        and (s0_min + margin) <= thr_s0 <= (s0_max - margin)
    )
    p_ok = p_hat < 0.01
    ci_ok = (
        thr_s0 is not None
        and np.isfinite(ci_low)
        and float(ci_low) > s0_min
    )
    power_ok = power_est >= 0.70

    if not power_ok:
        verdict_token = "INDETERMINATE"
        rationale = f"Power gate: detection_rate={power_est:.3f} < 0.70. Increase n or S0 range."
    elif p_ok and sesoi_ok and ci_ok:
        verdict_token = "ACCEPT"
        rationale = (
            f"Threshold detected: S0*={thr_s0:.3f}, p_hat={p_hat:.4f}<0.01, "
            f"CI99%=[{ci_low:.3f},{ci_high:.3f}] in interior [{s0_min+margin:.3f},{s0_max-margin:.3f}], "
            f"power={power_est:.3f}>=0.70."
        )
    else:
        reasons = []
        if not p_ok:
            reasons.append(f"p_hat={p_hat:.4f}>=0.01 (threshold not robustly detected)")
        if not sesoi_ok:
            thr_str = f"{thr_s0:.3f}" if thr_s0 is not None else "None"
            reasons.append(f"S0*={thr_str} not in interior [{s0_min+margin:.3f},{s0_max-margin:.3f}]")
        if not ci_ok:
            reasons.append(f"CI99% [{ci_low},{ci_high}] not valid")
        verdict_token = "REJECT" if thr_s0 is not None else "INDETERMINATE"
        rationale = "Triplet failed: " + "; ".join(reasons)

    summary = {
        "n": int(args.n),
        "seed": int(args.seed),
        "t_steps": int(args.t_steps),
        "S0_min": s0_min,
        "S0_max": s0_max,
        "threshold_S0": thr_s0,
        "p_hat": p_hat,
        "p_ok": bool(p_ok),
        "ci_99_low": float(ci_low),
        "ci_99_high": float(ci_high),
        "ci_ok": bool(ci_ok),
        "sesoi_ok": bool(sesoi_ok),
        "power_estimate": power_est,
        "power_ok": bool(power_ok),
        "verdict": verdict_token,
        "rationale": rationale,
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = {
        "test": "T7_progressive_S0_sweep",
        "verdict": verdict_token,
        "threshold_S0": thr_s0,
        "p_hat": p_hat,
        "p_ok": bool(p_ok),
        "ci_99_low": float(ci_low),
        "ci_99_high": float(ci_high),
        "ci_ok": bool(ci_ok),
        "sesoi_ok": bool(sesoi_ok),
        "power_estimate": power_est,
        "power_ok": bool(power_ok),
        "rationale": rationale,
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    (outdir / "verdict.txt").write_text(verdict_token, encoding="utf-8")

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
