"""
Robustesse (secondaire, non décisionnelle)

Ce script boucle sur des variantes de paramètres:
- poids ω pour V(t)
- poids α pour S(t)
- fenêtre Δ de lissage descriptif (rolling mean) sur V et S

Il réutilise les fonctions du pipeline CSV (run_synthetic_demo.py) pour éviter les doublons.

Sortie:
- robustness_results.csv

Usage:
python 04_Code/pipeline/run_robustness.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import argparse
import sys
from typing import Iterable

import numpy as np
import pandas as pd

# Allow direct execution from repo root: python 04_Code/pipeline/run_robustness.py
ROOT = Path(__file__).resolve().parents[1]  # 04_Code
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.run_synthetic_demo import (  # noqa: E402
    Weights,
    compute_V,
    compute_S,
    compute_capacity,
    compute_sigma,
    compute_C_simplified,
    detect_threshold,
)


def _renorm(w: list[float]) -> list[float]:
    s = float(sum(w))
    if s <= 0:
        raise ValueError("Somme des poids <= 0")
    return [float(x) / s for x in w]


def _variants(base: list[float], frac: float = 0.20) -> list[list[float]]:
    """
    Génère un petit ensemble de variantes: baseline + (i augmenté) + (i diminué), renormalisées.
    """
    out: list[list[float]] = []
    out.append(_renorm(base[:]))
    for i in range(len(base)):
        up = base[:]
        up[i] = up[i] * (1.0 + frac)
        out.append(_renorm(up))
        down = base[:]
        down[i] = down[i] * (1.0 - frac)
        out.append(_renorm(down))
    # dédoublonnage numérique grossier
    uniq = []
    seen = set()
    for v in out:
        key = tuple(round(x, 6) for x in v)
        if key not in seen:
            uniq.append(v)
            seen.add(key)
    return uniq


def _apply_smoothing(df: pd.DataFrame, cols: Iterable[str], delta: int) -> pd.DataFrame:
    if delta <= 1:
        return df
    df = df.copy()
    for _id, g in df.groupby("id", sort=False):
        idx = g.index
        for c in cols:
            df.loc[idx, c] = g[c].rolling(delta, min_periods=1).mean().values
    return df


def _symbolic_effect(df: pd.DataFrame, drop_frac: float = 0.35, gamma: float = 0.6) -> float:
    """
    Estime un effet moyen de la perturbation symbolique sur V.
    On réutilise la même logique que la figure V perturbée.
    Renvoie la différence moyenne (V_pert - V) en post intervention.
    """
    pert = df["perturb_symbolic"].fillna(0).astype(int)
    if pert.sum() == 0:
        return 0.0

    S_pert = df["S"] * np.where(pert == 1, 1.0 - drop_frac, 1.0)
    V_pert = df["V"] - gamma * (df["S"] - S_pert)

    start_idx = df.index[pert == 1][0]
    post = df.loc[start_idx:]
    return float((V_pert.loc[post.index] - post["V"]).mean())


def run_once(df_raw: pd.DataFrame, w: Weights, delta: int, k: float, m: int) -> dict:
    df = df_raw.sort_values(["id", "t"]).reset_index(drop=True).copy()

    df["V"] = compute_V(df, w)
    df["S"] = compute_S(df, w)

    # lissage descriptif si delta > 1
    df = _apply_smoothing(df, cols=["V", "S"], delta=delta)

    df["Cap"] = compute_capacity(df)
    df["Sigma"] = compute_sigma(df)

    out_parts = []
    for _id, g in df.groupby("id", sort=False):
        g = g.copy()
        g["C"] = compute_C_simplified(g)
        out_parts.append(g)
    df = pd.concat(out_parts, axis=0).reset_index(drop=True)

    df["delta_C"] = df.groupby("id")["C"].diff().fillna(0.0)
    threshold_idx, thr_value = detect_threshold(df["delta_C"], k=k, m=m)

    effect = _symbolic_effect(df)

    return {
        "delta": int(delta),
        "threshold_detected": bool(threshold_idx is not None),
        "threshold_idx": int(threshold_idx) if threshold_idx is not None else None,
        "threshold_t": float(df.loc[threshold_idx, "t"]) if threshold_idx is not None else None,
        "threshold_value": float(thr_value),
        "C_end": float(df["C"].iloc[-1]),
        "Sigma_mean": float(df["Sigma"].mean()),
        "V_mean": float(df["V"].mean()),
        "symbolic_effect_mean": float(effect),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--frac", type=float, default=0.20)
    ap.add_argument("--deltas", type=str, default="1,3,5,7")
    args = ap.parse_args()

    df_raw = pd.read_csv(args.input)

    # baseline weights
    base = Weights()
    omega_base = [base.omega_survie, base.omega_energie, base.omega_integrite, base.omega_persistance]
    alpha_base = [base.alpha_repertoire, base.alpha_codification, base.alpha_densite, base.alpha_fidelite]

    omega_vars = _variants(omega_base, frac=args.frac)
    alpha_vars = _variants(alpha_base, frac=args.frac)

    deltas = [int(x.strip()) for x in args.deltas.split(",") if x.strip()]
    deltas = [d for d in deltas if d >= 1]
    if not deltas:
        deltas = [1]

    rows = []
    for oi, omega in enumerate(omega_vars):
        for ai, alpha in enumerate(alpha_vars):
            w = Weights(
                omega_survie=omega[0],
                omega_energie=omega[1],
                omega_integrite=omega[2],
                omega_persistance=omega[3],
                alpha_repertoire=alpha[0],
                alpha_codification=alpha[1],
                alpha_densite=alpha[2],
                alpha_fidelite=alpha[3],
            )
            for d in deltas:
                r = run_once(df_raw, w=w, delta=d, k=args.k, m=args.m)
                r.update(
                    {
                        "omega_variant_id": oi,
                        "alpha_variant_id": ai,
                        "omega": ",".join(f"{x:.6f}" for x in omega),
                        "alpha": ",".join(f"{x:.6f}" for x in alpha),
                    }
                )
                rows.append(r)

    outdir = args.outdir
    tables = outdir / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    out = pd.DataFrame(rows)
    out.to_csv(tables / "robustness_results.csv", index=False)

    # petite synthèse utile
    stability = float(out["threshold_detected"].mean()) if len(out) else 0.0
    summary = pd.DataFrame(
        [
            {
                "n_variants": int(len(out)),
                "share_threshold_detected": stability,
                "k": float(args.k),
                "m": int(args.m),
                "frac": float(args.frac),
                "deltas": args.deltas,
            }
        ]
    )
    summary.to_csv(tables / "robustness_summary.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
