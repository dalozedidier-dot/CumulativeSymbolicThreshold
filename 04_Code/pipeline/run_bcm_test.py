#!/usr/bin/env python3
# run_bcm_test.py
#
# CLI runner for BCM-like plasticity with cut and reinjection schedules.
#
# Outputs:
# - tables/bcm_timeseries.csv
# - tables/summary.csv
# - figures/bcm_timeseries.png
# - verdict.txt
#
# Local verdict logic is intentionally minimal and deterministic.

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from bcm_plasticity import BCMConfig, build_input_schedule, simulate_bcm


def _robust_sd_mad(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    return float(1.4826 * mad) if mad > 0 else float(np.std(x))


def local_verdict_cut_reinject(
    df: pd.DataFrame, cut_start: int, cut_len: int, reinject_start: int, reinject_len: int
) -> str:
    """
    Minimal verdict based on weight changes:
    - cut effect must reduce w by at least 0.3 robust SD relative to pre-cut window.
    - reinjection effect must recover w by at least 0.3 robust SD relative to cut window.

    If both hold: ACCEPT.
    If both clearly fail: REJECT.
    Else: INDETERMINATE.
    """
    w = df["w"].to_numpy()

    pre = w[max(0, cut_start - 200) : cut_start]
    cut = w[cut_start : cut_start + cut_len]
    reinj = w[reinject_start : reinject_start + reinject_len]

    if len(pre) < 10 or len(cut) < 10 or len(reinj) < 10:
        return "INDETERMINATE"

    sd = _robust_sd_mad(pre)
    sd = sd if sd > 1e-9 else float(np.std(pre)) + 1e-9

    pre_mean = float(np.mean(pre))
    cut_mean = float(np.mean(cut))
    reinj_mean = float(np.mean(reinj))

    cut_drop = pre_mean - cut_mean
    reinj_gain = reinj_mean - cut_mean

    ok_cut = cut_drop >= 0.3 * sd
    ok_reinj = reinj_gain >= 0.3 * sd

    if ok_cut and ok_reinj:
        return "ACCEPT"
    if (not ok_cut) and (not ok_reinj):
        return "REJECT"
    return "INDETERMINATE"


def main() -> int:
    ap = argparse.ArgumentParser(description="BCM-like plasticity demo with cut and reinjection schedules.")
    ap.add_argument("--outdir", required=True, help="Output directory.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-steps", type=int, default=1200)
    ap.add_argument("--input-amp", type=float, default=0.7)
    ap.add_argument("--noise-sigma", type=float, default=0.05)
    ap.add_argument("--eta", type=float, default=0.002)
    ap.add_argument("--tau-bar", type=float, default=80.0)
    ap.add_argument("--c0", type=float, default=0.25)
    ap.add_argument("--p", type=float, default=2.0)
    ap.add_argument("--w0", type=float, default=0.6)

    ap.add_argument("--cut-start", type=int, default=500)
    ap.add_argument("--cut-len", type=int, default=120)
    ap.add_argument("--reinject-start", type=int, default=750)
    ap.add_argument("--reinject-len", type=int, default=140)
    ap.add_argument("--reinject-amp", type=float, default=0.9)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)

    x = build_input_schedule(
        n_steps=args.n_steps,
        input_amp=args.input_amp,
        cut_start=args.cut_start,
        cut_len=args.cut_len,
        reinject_start=args.reinject_start,
        reinject_len=args.reinject_len,
        reinject_amp=args.reinject_amp,
    )

    cfg = BCMConfig(
        n_steps=args.n_steps,
        seed=args.seed,
        input_amp=args.input_amp,
        noise_sigma=args.noise_sigma,
        eta=args.eta,
        tau_bar=args.tau_bar,
        c0=args.c0,
        p=args.p,
        w0=args.w0,
    )

    df, metrics = simulate_bcm(cfg, x=x)
    df.to_csv(tabdir / "bcm_timeseries.csv", index=False)

    verdict = local_verdict_cut_reinject(df, args.cut_start, args.cut_len, args.reinject_start, args.reinject_len)
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    summary = {
        "test": "Test9B_bcm_cut_reinject",
        "n_steps": int(args.n_steps),
        "cut_start": int(args.cut_start),
        "cut_len": int(args.cut_len),
        "reinject_start": int(args.reinject_start),
        "reinject_len": int(args.reinject_len),
        "verdict": verdict,
        **{k: float(v) for k, v in metrics.items()},
    }
    pd.DataFrame([summary]).to_csv(tabdir / "summary.csv", index=False)

    plt.figure(figsize=(10, 6))
    plt.plot(df["t"], df["w"], label="w")
    plt.plot(df["t"], df["theta_M"], label="theta_M", linestyle="--")
    plt.plot(df["t"], df["x"], label="x (input)", alpha=0.6)
    plt.axvspan(args.cut_start, args.cut_start + args.cut_len, alpha=0.15, label="cut")
    plt.axvspan(args.reinject_start, args.reinject_start + args.reinject_len, alpha=0.15, label="reinjection")
    plt.xlabel("t")
    plt.title("BCM demo: weight, threshold, and input schedule")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figdir / "bcm_timeseries.png", dpi=150)
    plt.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
