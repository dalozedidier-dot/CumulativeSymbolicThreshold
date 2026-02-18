#!/usr/bin/env python3
"""Generate a deterministic synthetic dataset designed to trigger a detectable
C-threshold under the repo's default settings.

Output columns match the pipeline expectations:
    t, O, R, I, demande_env,
    survie, energie_nette, integrite, persistance,
    repertoire, codification, densite_transmission, fidelite
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(
    n: int = 140,
    seed: int = 42,
    t0: int = 60,
    base_v: float = 0.55,
    base_s: float = 0.35,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n)

    O = np.ones(n) * 0.9 + rng.normal(0, 0.002, n)
    R = np.ones(n) * 0.9 + rng.normal(0, 0.002, n)
    I = np.ones(n) * 0.9 + rng.normal(0, 0.002, n)

    demande_env = np.ones(n) * 0.8 + rng.normal(0, 0.003, n)
    demande_env[50:] = 0.95 + rng.normal(0, 0.003, n - 50)
    demande_env[90:] = 1.05 + rng.normal(0, 0.003, n - 90)

    # Viability proxies (V)
    survie = np.ones(n) * base_v + rng.normal(0, 0.003, n)
    energie_nette = np.ones(n) * base_v + rng.normal(0, 0.003, n)
    integrite = np.ones(n) * base_v + rng.normal(0, 0.003, n)
    persistance = np.ones(n) * base_v + rng.normal(0, 0.003, n)

    # Symbolic proxies (S)
    repertoire = np.ones(n) * base_s + rng.normal(0, 0.003, n)
    codification = np.ones(n) * base_s + rng.normal(0, 0.003, n)
    densite_transmission = np.ones(n) * base_s + rng.normal(0, 0.003, n)
    fidelite = np.ones(n) * base_s + rng.normal(0, 0.003, n)

    # Three-step symbolic ramp to produce sustained delta_C > threshold.
    ramp_s = np.array([0.25, 0.28, 0.30])
    for k, inc in enumerate(ramp_s):
        idx = t0 + k
        if idx >= n:
            break
        for arr in (repertoire, codification, densite_transmission, fidelite):
            arr[idx:] += inc

    # Small viability improvement (optional, keeps realism)
    ramp_v = np.array([0.03, 0.03, 0.03])
    for k, inc in enumerate(ramp_v):
        idx = t0 + k
        if idx >= n:
            break
        for arr in (survie, energie_nette, integrite, persistance):
            arr[idx:] += inc

    # Clamp to [0, 1]
    for arr in (
        survie,
        energie_nette,
        integrite,
        persistance,
        repertoire,
        codification,
        densite_transmission,
        fidelite,
    ):
        np.clip(arr, 0.0, 1.0, out=arr)

    return pd.DataFrame(
        {
            "t": t,
            "O": O,
            "R": R,
            "I": I,
            "demande_env": demande_env,
            "survie": survie,
            "energie_nette": energie_nette,
            "integrite": integrite,
            "persistance": persistance,
            "repertoire": repertoire,
            "codification": codification,
            "densite_transmission": densite_transmission,
            "fidelite": fidelite,
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=str,
        default="03_Data/synthetic/synthetic_with_threshold.csv",
        help="Output CSV path.",
    )
    ap.add_argument("--n", type=int, default=140)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--t0", type=int, default=60)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    df = generate(n=args.n, seed=args.seed, t0=args.t0)
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
