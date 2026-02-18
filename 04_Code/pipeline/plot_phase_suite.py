#!/usr/bin/env python3
"""
plot_phase_suite.py

Minimal visualization pack for the ORI-C project.
This script does not change the framework. It only produces figures.

Inputs
- A CSV with at least columns: t, Sigma, C, V
- Optional columns: U, threshold_hit (0/1)

Outputs (under --outdir)
- figures/
  - V_pre_post_threshold.png
  - phase_C_vs_Sigma.png
  - hysteresis_C_vs_stress.png  (uses U if present, else Sigma)
  - yinyang_ORIC.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def ensure_dirs(outdir: Path) -> Path:
    figs = outdir / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    return figs


def plot_v_pre_post(df: pd.DataFrame, figs: Path, default_t0: int = 50) -> None:
    t = df["t"].to_numpy()
    V = df["V"].to_numpy()

    if "threshold_hit" in df.columns and (df["threshold_hit"].astype(int).sum() > 0):
        t0 = int(df.loc[df["threshold_hit"].astype(int) == 1, "t"].iloc[0])
        label = "threshold_hit"
    else:
        t0 = int(default_t0)
        label = "t0"

    plt.figure(figsize=(10, 5))
    plt.plot(t, V, label="V(t)")
    plt.axvline(x=t0, linestyle="--", label=label)
    plt.xlabel("t")
    plt.ylabel("V")
    plt.title("V(t) pre and post marker")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figs / "V_pre_post_threshold.png", dpi=160)
    plt.close()


def plot_phase(df: pd.DataFrame, figs: Path) -> None:
    plt.figure(figsize=(6, 6))
    plt.scatter(df["Sigma"], df["C"], s=14)
    plt.xlabel("Sigma(t)")
    plt.ylabel("C(t)")
    plt.title("Phase plot: C versus Sigma")
    plt.tight_layout()
    plt.savefig(figs / "phase_C_vs_Sigma.png", dpi=160)
    plt.close()


def plot_hysteresis(df: pd.DataFrame, figs: Path) -> None:
    if "U" in df.columns:
        x = df["U"].to_numpy()
        xlabel = "U(t)"
    else:
        x = df["Sigma"].to_numpy()
        xlabel = "Sigma(t)"

    y = df["C"].to_numpy()

    plt.figure(figsize=(8, 6))
    plt.plot(x, y)
    plt.xlabel(xlabel)
    plt.ylabel("C(t)")
    plt.title("Hysteresis style plot: C versus stress proxy")
    plt.tight_layout()
    plt.savefig(figs / "hysteresis_C_vs_stress.png", dpi=160)
    plt.close()


def plot_yinyang(figs: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    outer = plt.Circle((0, 0), 1.0, fill=False)
    ax.add_patch(outer)

    theta = np.linspace(-np.pi / 2, np.pi / 2, 300)
    x1 = np.cos(theta)
    y1 = np.sin(theta)

    ax.fill_between(x1, y1, -y1, where=(x1 <= 0), interpolate=True)
    ax.fill_between(x1, y1, -y1, where=(x1 >= 0), interpolate=True, color="white")

    small1 = plt.Circle((0, 0.5), 0.2, color="white")
    small2 = plt.Circle((0, -0.5), 0.2, color="black")
    ax.add_patch(small1)
    ax.add_patch(small2)

    ax.text(-0.55, 0.55, "O", fontsize=18, color="black")
    ax.text(0.45, 0.55, "R", fontsize=18, color="black")
    ax.text(-0.55, -0.65, "I", fontsize=18, color="black")
    ax.text(0.45, -0.65, "C", fontsize=18, color="black")

    ax.set_aspect("equal")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(figs / "yinyang_ORIC.png", dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--default_t0", type=int, default=50)
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    required = {"t", "Sigma", "C", "V"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")

    figs = ensure_dirs(Path(args.outdir))
    plot_v_pre_post(df, figs, default_t0=args.default_t0)
    plot_phase(df, figs)
    plot_hysteresis(df, figs)
    plot_yinyang(figs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
