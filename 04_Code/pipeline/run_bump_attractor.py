#!/usr/bin/env python3
# run_bump_attractor.py
#
# Lightweight bump attractor demo (ring network).
# Purpose: provide an optional "neuro extension" testbed consistent with ORI-C style:
# - reproducible runs via seeds
# - metrics + local verdict
# - deterministic outputs in an outdir
#
# This script intentionally avoids heavy dependencies.

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class BumpConfig:
    n: int = 128
    dt: float = 1.0
    n_steps: int = 800
    tau: float = 10.0
    gain: float = 1.8
    sigma_noise: float = 0.06
    bump_center_deg: float = 90.0
    bump_sigma_deg: float = 12.0
    input_amp: float = 0.8
    input_steps: int = 60
    seed: int = 42


def _angles_deg(n: int) -> np.ndarray:
    return np.linspace(0.0, 360.0, n, endpoint=False)


def _wrap_deg(a: float) -> float:
    # Map to [-180, 180)
    x = (a + 180.0) % 360.0 - 180.0
    return float(x)


def _circ_mean_deg(angles_deg: np.ndarray, weights: np.ndarray) -> float:
    angles_rad = np.deg2rad(angles_deg)
    x = np.sum(weights * np.cos(angles_rad))
    y = np.sum(weights * np.sin(angles_rad))
    if x == 0.0 and y == 0.0:
        return float("nan")
    return float(np.rad2deg(np.arctan2(y, x)) % 360.0)


def _make_ring_kernel(n: int, kappa: float = 10.0) -> np.ndarray:
    """
    von Mises-like kernel on a ring, normalized.
    Larger kappa gives narrower coupling.
    """
    angles_rad = np.deg2rad(_angles_deg(n))
    kernel = np.exp(kappa * (np.cos(angles_rad) - 1.0))
    kernel = kernel / np.sum(kernel)
    return kernel


def simulate_bump(cfg: BumpConfig) -> Tuple[pd.DataFrame, Dict[str, float]]:
    rng = np.random.default_rng(cfg.seed)

    n = cfg.n
    angles = _angles_deg(n)
    kernel = _make_ring_kernel(n, kappa=10.0)

    r = np.zeros(n, dtype=float)

    center = cfg.bump_center_deg
    d = np.array([_wrap_deg(a - center) for a in angles], dtype=float)
    inp_profile = cfg.input_amp * np.exp(-0.5 * (d / cfg.bump_sigma_deg) ** 2)

    rows = []
    for t in range(cfg.n_steps):
        ext = inp_profile if t < cfg.input_steps else 0.0

        rec = cfg.gain * np.fft.ifft(np.fft.fft(r) * np.fft.fft(kernel)).real

        noise = rng.normal(0.0, cfg.sigma_noise, size=n)
        drive = rec + ext + noise
        drive = np.maximum(0.0, drive)

        r = r + (cfg.dt / cfg.tau) * (-r + drive)

        if t % 5 == 0 or t == cfg.n_steps - 1:
            peak_deg = _circ_mean_deg(angles, r)
            peak_val = float(np.max(r))
            half = 0.5 * peak_val
            frac_half = float(np.mean(r >= half)) if peak_val > 0 else 0.0
            width_deg = 360.0 * frac_half
            rows.append({"t": t, "peak_deg": peak_deg, "peak_val": peak_val, "width_deg": width_deg})

    df = pd.DataFrame(rows)

    tail = df[df["t"] >= int(cfg.n_steps * 0.66)].copy()
    if tail["peak_deg"].isna().all():
        drift_abs = float("inf")
    else:
        drift = tail["peak_deg"].apply(lambda a: _wrap_deg(a - cfg.bump_center_deg))
        drift_abs = float(np.nanmedian(np.abs(drift)))

    width_med = float(np.nanmedian(tail["width_deg"])) if not tail.empty else float("nan")
    peak_med = float(np.nanmedian(tail["peak_val"])) if not tail.empty else 0.0

    if math.isfinite(drift_abs) and width_med > 0:
        persistence = (peak_med / (1.0 + width_med / 90.0)) * (1.0 / (1.0 + drift_abs / 30.0))
    else:
        persistence = 0.0

    metrics = {
        "drift_abs_deg_median": drift_abs,
        "width_deg_median": width_med,
        "peak_val_median": peak_med,
        "persistence_score": float(persistence),
    }
    return df, metrics


def local_verdict(persistence_scores: np.ndarray) -> str:
    """
    Minimal local verdict rule:
    - ACCEPT if median persistence >= 0.35 and at least 80% runs have persistence >= 0.25.
    - REJECT if median persistence <= 0.10 and at least 80% runs have persistence <= 0.12.
    - INDETERMINATE otherwise.
    """
    med = float(np.median(persistence_scores))
    hi = float(np.mean(persistence_scores >= 0.25))
    lo = float(np.mean(persistence_scores <= 0.12))

    if med >= 0.35 and hi >= 0.80:
        return "ACCEPT"
    if med <= 0.10 and lo >= 0.80:
        return "REJECT"
    return "INDETERMINATE"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a ring bump attractor demo and write metrics + figures.")
    ap.add_argument("--outdir", required=True, help="Output directory (will create figures/ and tables/).")
    ap.add_argument("--n-runs", type=int, default=50, help="Number of independent runs (different seeds).")
    ap.add_argument("--seed", type=int, default=42, help="Master seed for run seeds.")
    ap.add_argument("--gain", type=float, default=1.8, help="Recurrent gain (higher stabilizes bumps).")
    ap.add_argument("--sigma-noise", type=float, default=0.06, help="Noise standard deviation.")
    ap.add_argument("--n-steps", type=int, default=800, help="Total simulation steps.")
    ap.add_argument("--n", type=int, default=128, help="Number of neurons on the ring.")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)

    master_rng = np.random.default_rng(args.seed)
    run_seeds = master_rng.integers(low=0, high=2**32 - 1, size=args.n_runs, dtype=np.uint32)

    run_rows = []
    example_df = None

    for i, s in enumerate(run_seeds):
        cfg = BumpConfig(n=args.n, n_steps=args.n_steps, gain=args.gain, sigma_noise=args.sigma_noise, seed=int(s))
        df, met = simulate_bump(cfg)
        if example_df is None:
            example_df = df.copy()
        run_rows.append({"run": i, "seed": int(s), **met})

    runs_df = pd.DataFrame(run_rows)
    runs_df.to_csv(tabdir / "bump_runs.csv", index=False)

    verdict = local_verdict(runs_df["persistence_score"].to_numpy())

    summary = {
        "test": "Test9A_bump_attractor",
        "n_runs": int(args.n_runs),
        "gain": float(args.gain),
        "sigma_noise": float(args.sigma_noise),
        "persistence_median": float(runs_df["persistence_score"].median()),
        "persistence_mean": float(runs_df["persistence_score"].mean()),
        "persistence_p80": float(np.percentile(runs_df["persistence_score"], 80)),
        "drift_abs_deg_median": float(runs_df["drift_abs_deg_median"].median()),
        "width_deg_median": float(runs_df["width_deg_median"].median()),
        "verdict": verdict,
    }
    pd.DataFrame([summary]).to_csv(tabdir / "summary.csv", index=False)
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    plt.figure(figsize=(9, 4))
    plt.hist(runs_df["persistence_score"].to_numpy(), bins=20)
    plt.xlabel("Persistence score")
    plt.ylabel("Count")
    plt.title("Bump attractor persistence score distribution")
    plt.tight_layout()
    plt.savefig(figdir / "bump_persistence_hist.png", dpi=150)
    plt.close()

    drift_vals = runs_df["drift_abs_deg_median"].replace([np.inf], np.nan).dropna().to_numpy()
    if len(drift_vals):
        plt.figure(figsize=(9, 4))
        plt.hist(drift_vals, bins=20)
        plt.xlabel("Median absolute drift (deg)")
        plt.ylabel("Count")
        plt.title("Bump drift distribution")
        plt.tight_layout()
        plt.savefig(figdir / "bump_drift_hist.png", dpi=150)
        plt.close()

    if example_df is not None:
        plt.figure(figsize=(9, 4))
        plt.plot(example_df["t"], example_df["peak_val"], label="peak_val")
        plt.twinx()
        plt.plot(example_df["t"], example_df["width_deg"], linestyle="--", label="width_deg")
        plt.title("Example run: peak and width over time")
        plt.xlabel("t")
        plt.tight_layout()
        plt.savefig(figdir / "bump_example_peak_width.png", dpi=150)
        plt.close()

        plt.figure(figsize=(9, 4))
        plt.plot(example_df["t"], example_df["peak_deg"])
        plt.axhline(90.0, linestyle="--")
        plt.title("Example run: bump center (deg) over time")
        plt.xlabel("t")
        plt.ylabel("deg")
        plt.tight_layout()
        plt.savefig(figdir / "bump_example_center.png", dpi=150)
        plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
