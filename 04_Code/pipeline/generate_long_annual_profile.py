#!/usr/bin/env python3
"""04_Code/pipeline/generate_long_annual_profile.py

Generate a long synthetic annual-profile time series (200+ rows) in the
ORI-C real-data CSV format (columns: t, O, R, I, demand, S).

The series simulates a slow-moving annual trajectory that includes:
  - a pre-threshold phase (gradual accumulation, O/R/I fluctuating)
  - a symbolic injection ramp around t0
  - a post-threshold cumulative regime (S self-reinforcing)

This produces a dataset long enough for all causal tests
(Granger, VAR, cointegration) to have statistical power, while
retaining the slow annual dynamics of real Eurostat-style data.

Output columns (ORI-C standard real-data format):
  t, O, R, I, demand, S

Usage:
  python 04_Code/pipeline/generate_long_annual_profile.py \\
      --out 03_Data/synthetic/synthetic_long_annual.csv \\
      --n 250 --seed 42 --t0 100

  python 04_Code/pipeline/generate_long_annual_profile.py \\
      --out 03_Data/synthetic/synthetic_long_annual_no_thr.csv \\
      --n 250 --seed 7 --no-transition
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(
    n: int = 250,
    seed: int = 42,
    t0: int = 100,
    transition: bool = True,
    base_O: float = 0.60,
    base_R: float = 0.55,
    base_I: float = 0.50,
    base_S: float = 0.20,
    noise_scale: float = 0.015,
) -> pd.DataFrame:
    """Generate a long synthetic annual-profile ORI-C dataset.

    Parameters
    ----------
    n:
        Total number of annual time steps (rows).  Must be > 50.
    seed:
        NumPy random seed for reproducibility.
    t0:
        Index at which the symbolic transition begins.
        Ignored when ``transition=False``.
    transition:
        If True, inject a symbolic ramp at t0 that triggers the cumulative
        regime.  If False, produce a flat pre-threshold-only series.
    base_O, base_R, base_I, base_S:
        Baseline levels for the proxies in [0, 1].
    noise_scale:
        Std of the annual noise term (kept small to mimic annual smoothness).
    """
    if n < 51:
        raise ValueError(f"n must be > 50 for statistical tests, got {n}")
    if transition and t0 >= n - 10:
        raise ValueError(f"t0={t0} leaves < 10 post-transition steps for n={n}")

    rng = np.random.default_rng(int(seed))
    t = np.arange(n, dtype=int)

    # ── Slow-moving O, R, I with a gentle upward trend and annual noise ──
    trend = np.linspace(0.0, 0.08, n)          # +8 pp drift over full horizon
    O = np.clip(base_O + trend + rng.normal(0, noise_scale, n), 0.0, 1.0)
    R = np.clip(base_R + trend * 0.7 + rng.normal(0, noise_scale, n), 0.0, 1.0)
    I = np.clip(base_I + trend * 0.5 + rng.normal(0, noise_scale, n), 0.0, 1.0)

    # ── Demand: slightly above Cap baseline, with a late-period surge ────
    cap = O * R * I
    demand = cap * 0.85 + rng.normal(0, noise_scale * 0.5, n)
    if n >= 50:
        # moderate demand surge in the last third
        surge_start = int(n * 0.65)
        demand[surge_start:] += np.linspace(0.0, 0.12, n - surge_start)
    demand = np.clip(demand, 0.0, 1.0)

    # ── Symbolic stock S ──────────────────────────────────────────────────
    S = np.ones(n) * base_S + rng.normal(0, noise_scale * 0.5, n)

    if transition and t0 < n:
        # Three-step ramp then sustained accumulation
        ramp_steps = min(3, n - t0)
        ramp_heights = [0.15, 0.20, 0.25]
        for k in range(ramp_steps):
            idx = t0 + k
            if idx < n:
                S[idx:] += ramp_heights[k]
        # Gradual self-reinforcing growth post-ramp
        post_start = t0 + ramp_steps
        if post_start < n:
            post_len = n - post_start
            S[post_start:] += np.linspace(0.0, 0.15, post_len)

    S = np.clip(S, 0.0, 1.0)

    return pd.DataFrame(
        {
            "t": t,
            "O": np.round(O, 6),
            "R": np.round(R, 6),
            "I": np.round(I, 6),
            "demand": np.round(demand, 6),
            "S": np.round(S, 6),
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a long synthetic annual-profile ORI-C dataset."
    )
    ap.add_argument(
        "--out",
        type=str,
        default="03_Data/synthetic/synthetic_long_annual.csv",
        help="Output CSV path.",
    )
    ap.add_argument("--n", type=int, default=250, help="Number of annual rows (default: 250).")
    ap.add_argument("--seed", type=int, default=42, help="Random seed.")
    ap.add_argument("--t0", type=int, default=100, help="Transition start index (default: 100).")
    ap.add_argument(
        "--no-transition",
        action="store_true",
        help="Generate a pre-threshold-only series (no symbolic ramp).",
    )
    ap.add_argument("--noise-scale", type=float, default=0.015, help="Annual noise std (default: 0.015).")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    df = generate(
        n=int(args.n),
        seed=int(args.seed),
        t0=int(args.t0),
        transition=not bool(args.no_transition),
        noise_scale=float(args.noise_scale),
    )
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows, transition={'no' if args.no_transition else f'at t={args.t0}'})")


if __name__ == "__main__":
    main()
