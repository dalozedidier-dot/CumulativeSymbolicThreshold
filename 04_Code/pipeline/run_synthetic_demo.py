#!/usr/bin/env python3
"""
04_Code/pipeline/run_synthetic_demo.py

This module serves two roles:

1) Library: provides compute_* helpers used by run_robustness.py
2) CLI: processes a synthetic CSV into derived variables + threshold detection,
        and writes outputs to an outdir (tables + figures).

Design notes:
- All transformations are deterministic given the input CSV and flags.
- Columns are added, never removed.
- The script is defensive: it tolerates missing optional columns.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# -----------------------------
# Helpers (shared with robustness)
# -----------------------------

@dataclass(frozen=True)
class Weights:
    # ORI aggregation (C uses these upstream only if needed)
    wO: float = 0.4
    wR: float = 0.35
    wI: float = 0.25

    # Viability V proxy
    w_survie: float = 0.35
    w_energie: float = 0.35
    w_integrite: float = 0.30

    # Symbolic stock S proxy
    w_repertoire: float = 0.25
    w_codification: float = 0.25
    w_densite: float = 0.25
    w_fidelite: float = 0.25


def _col(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce").fillna(default)
    return pd.Series(np.full(len(df), default), index=df.index, name=name)


def compute_capacity(df: pd.DataFrame, scale: float = 1000.0) -> pd.Series:
    """
    Cap(t) principal: projection explicite O(t) * R(t) * I(t), scaled.
    """
    O = _col(df, "O", 0.0)
    R = _col(df, "R", 0.0)
    I = _col(df, "I", 0.0)
    cap = (O * R * I) * float(scale)
    return cap.rename("Cap")


def compute_sigma(df: pd.DataFrame, demand_col: str = "demande_env") -> pd.Series:
    """
    Sigma(t) = max(0, D(E(t)) - Cap(t)).
    demand_col defaults to 'demande_env' but falls back to 'D' if needed.
    """
    if demand_col not in df.columns and "D" in df.columns:
        demand_col = "D"
    D = _col(df, demand_col, 0.0)
    Cap = _col(df, "Cap", 0.0)
    sigma = np.maximum(0.0, (D - Cap).to_numpy())
    return pd.Series(sigma, index=df.index, name="Sigma")


def compute_V(df: pd.DataFrame, w: Weights) -> pd.Series:
    """
    V(t) proxy: weighted non-compensatory-ish blend.
    Preference: use survivie, energie_nette, integrite, persistance if present.
    Otherwise: fallback to (O,R,I) min as a weak viability proxy.

    Output is clipped to [0,1].
    """
    if {"survie", "energie_nette", "integrite"}.issubset(df.columns):
        survie = _col(df, "survie", 0.0)
        energie = _col(df, "energie_nette", 0.0)
        integrite = _col(df, "integrite", 0.0)
        pers = _col(df, "persistance", 1.0)
        v = (
            w.w_survie * survie
            + w.w_energie * energie
            + w.w_integrite * integrite
        )
        v = v * pers
        v = np.clip(v.to_numpy(), 0.0, 1.0)
        return pd.Series(v, index=df.index, name="V")
    else:
        O = _col(df, "O", 0.0)
        R = _col(df, "R", 0.0)
        I = _col(df, "I", 0.0)
        v = np.minimum(np.minimum(O, R), I)
        v = np.clip(v.to_numpy(), 0.0, 1.0)
        return pd.Series(v, index=df.index, name="V")


def compute_S(df: pd.DataFrame, w: Weights) -> pd.Series:
    """
    S(t) proxy: transmissible symbolic stock.

    Uses repertoire, codification, densite_transmission, fidelite if available.
    Otherwise uses a fallback based on (1 - Sigma_norm) to avoid NaNs.
    """
    required = {"repertoire", "codification", "densite_transmission", "fidelite"}
    if required.issubset(df.columns):
        rep = _col(df, "repertoire", 0.0)
        cod = _col(df, "codification", 0.0)
        den = _col(df, "densite_transmission", 0.0)
        fid = _col(df, "fidelite", 0.0)
        s = (
            w.w_repertoire * rep
            + w.w_codification * cod
            + w.w_densite * den
            + w.w_fidelite * fid
        )
        s = np.clip(s.to_numpy(), 0.0, 1.0)
        return pd.Series(s, index=df.index, name="S")

    # Fallback: higher mismatch -> lower symbolic stock (crude but deterministic)
    sigma = _col(df, "Sigma", 0.0).to_numpy()
    if sigma.max() > 0:
        sigma_norm = sigma / (sigma.max() + 1e-12)
        s = 1.0 - sigma_norm
    else:
        s = np.ones_like(sigma)
    s = np.clip(s, 0.0, 1.0)
    return pd.Series(s, index=df.index, name="S")


def compute_C_simplified(df: pd.DataFrame, alpha: float = 0.1, beta: float = 0.5, gamma: float = 0.1) -> pd.Series:
    """
    C(t+1) = C(t) + beta * S(t) - gamma * V(t)
    with an optional alpha applied to Sigma if S is missing.

    Assumes df already contains S and V.
    """
    S = _col(df, "S", 0.0).to_numpy()
    V = _col(df, "V", 0.0).to_numpy()
    C = np.zeros(len(df), dtype=float)
    for i in range(1, len(df)):
        C[i] = C[i - 1] + beta * S[i - 1] - gamma * V[i - 1]
    return pd.Series(C, index=df.index, name="C")


def detect_threshold(delta_C: pd.Series, k: float = 2.5, m: int = 3) -> Tuple[Optional[int], float]:
    """
    Detect threshold in delta_C using global mean/std:
    threshold = mean + k * std
    hit if delta_C > threshold for m consecutive steps.

    Returns (index_label, threshold_value).
    """
    x = pd.to_numeric(delta_C, errors="coerce").fillna(0.0)
    mu = float(x.mean())
    sd = float(x.std(ddof=1)) if len(x) > 1 else 0.0
    thr = mu + float(k) * sd
    above = x > thr
    if m <= 1:
        hit = above
    else:
        hit = above.rolling(window=m, min_periods=m).sum() >= m
    if bool(hit.any()):
        idx = hit[hit].index[0]
        return idx, thr
    return None, thr


# -----------------------------
# CLI
# -----------------------------

def _make_dirs(outdir: Path) -> tuple[Path, Path]:
    figdir = outdir / "figures"
    tabdir = outdir / "tables"
    figdir.mkdir(parents=True, exist_ok=True)
    tabdir.mkdir(parents=True, exist_ok=True)
    return figdir, tabdir


def _plot_C_with_threshold(df: pd.DataFrame, thr_idx: Optional[int], outpath: Path) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(df["t"], df["C"], label="C(t)")
    if thr_idx is not None:
        t0 = float(df.loc[thr_idx, "t"])
        plt.axvline(t0, linestyle="--", label="threshold hit")
    plt.xlabel("t")
    plt.ylabel("C")
    plt.title("C(t) with threshold hit marker")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def _plot_V_perturbation(df: pd.DataFrame, outpath: Path) -> None:
    plt.figure(figsize=(10, 5))
    if "V" in df.columns:
        plt.plot(df["t"], df["V"], label="V(t)")
    if "perturb_symbolic" in df.columns:
        plt.plot(df["t"], _col(df, "perturb_symbolic", 0.0), label="perturb_symbolic")
    plt.xlabel("t")
    plt.ylabel("value")
    plt.title("V(t) and symbolic perturbation proxy")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to synthetic CSV")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--cap-scale", type=float, default=1000.0)
    args = ap.parse_args()

    inp = Path(args.input)
    outdir = Path(args.outdir)
    figdir, tabdir = _make_dirs(outdir)

    df = pd.read_csv(inp)
    if "t" not in df.columns:
        df["t"] = np.arange(len(df), dtype=int)

    w = Weights()

    df["Cap"] = compute_capacity(df, scale=args.cap_scale)
    df["Sigma"] = compute_sigma(df)
    df["V"] = compute_V(df, w)
    df["S"] = compute_S(df, w)
    df["C"] = compute_C_simplified(df)

    df["delta_C"] = df["C"].diff().fillna(0.0)
    thr_idx, thr_val = detect_threshold(df["delta_C"], k=args.k, m=args.m)
    df["threshold_value"] = thr_val
    df["threshold_hit"] = 0
    if thr_idx is not None:
        df.loc[thr_idx, "threshold_hit"] = 1

    # Save tables
    processed = tabdir / "processed_synthetic.csv"
    df.to_csv(processed, index=False)

    summary = {
        "input": str(inp),
        "n": int(len(df)),
        "threshold_detected": bool(thr_idx is not None),
        "threshold_index": None if thr_idx is None else int(thr_idx),
        "k": float(args.k),
        "m": int(args.m),
        "threshold_value": float(thr_val),
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = {
        "test": "synthetic_demo_threshold",
        "verdict": "ACCEPT" if thr_idx is not None else "INDETERMINATE",
        "threshold_detected": bool(thr_idx is not None),
        "threshold_value": float(thr_val),
    }
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    # Figures
    _plot_C_with_threshold(df, thr_idx, figdir / "c_t_with_threshold.png")
    _plot_V_perturbation(df, figdir / "v_t_perturbation.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
