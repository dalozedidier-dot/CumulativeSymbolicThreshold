"""
Démo end to end sur données synthétiques

Ce script:
- Lit un CSV minimal
- Calcule V(t), Cap(t), Sigma(t), S(t)
- Calcule C(t) en version simplifiée
- Détecte un seuil basique sur ΔC(t)
- Sauvegarde 2 figures
  1) C(t) avec seuil
  2) V avant et après une perturbation symbolique

Hypothèses de démo:
- V(t) et S(t) sont des agrégations pondérées
- C(t) augmente quand ΔS > 0 et ΔV > 0
- La perturbation symbolique est indiquée par perturb_symbolic (0 ou 1)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class Weights:
    omega_survie: float = 0.25
    omega_energie: float = 0.25
    omega_integrite: float = 0.25
    omega_persistance: float = 0.25
    alpha_repertoire: float = 0.25
    alpha_codification: float = 0.25
    alpha_densite: float = 0.25
    alpha_fidelite: float = 0.25


def compute_V(df: pd.DataFrame, w: Weights) -> pd.Series:
    return (
        w.omega_survie * df["survie"]
        + w.omega_energie * df["energie_nette"]
        + w.omega_integrite * df["integrite"]
        + w.omega_persistance * df["persistance"]
    )


def compute_S(df: pd.DataFrame, w: Weights) -> pd.Series:
    return (
        w.alpha_repertoire * df["repertoire"]
        + w.alpha_codification * df["codification"]
        + w.alpha_densite * df["densite_transmission"]
        + w.alpha_fidelite * df["fidelite"]
    )


def compute_capacity(df: pd.DataFrame) -> pd.Series:
    return df["O"] * df["R"] * df["I"]


def compute_sigma(df: pd.DataFrame) -> pd.Series:
    return (df["demande_env"] - df["Cap"]).clip(lower=0.0)


def compute_C_simplified(df: pd.DataFrame) -> pd.Series:
    # Simplification: cumul des gains lorsque S et V montent ensemble.
    dS = df["S"].diff().fillna(0.0)
    dV = df["V"].diff().fillna(0.0)
    contrib = np.where((dS > 0) & (dV > 0), dV, 0.0)
    return pd.Series(contrib, index=df.index).cumsum()


def detect_threshold(delta_C: pd.Series, k: float, m: int, ref_frac: float = 0.4) -> tuple[int | None, float]:
    n = len(delta_C)
    ref_n = max(3, int(np.floor(ref_frac * n)))
    ref = delta_C.iloc[:ref_n]
    mu = float(ref.mean())
    sigma = float(ref.std(ddof=1)) if ref_n > 1 else 0.0
    thr = mu + k * sigma

    above = delta_C > thr
    run = 0
    for i, ok in enumerate(above):
        run = run + 1 if bool(ok) else 0
        if run >= m:
            return i - m + 1, thr
    return None, thr


def plot_C_with_threshold(df: pd.DataFrame, outpath: Path, threshold_idx: int | None, thr_value: float) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(df["t"], df["C"], label="C(t)")
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xlabel("t")
    ax.set_ylabel("C(t)")
    ax.set_title("C(t) et franchissement de seuil sur ΔC(t)")
    if threshold_idx is not None:
        t0 = float(df.loc[threshold_idx, "t"])
        ax.axvline(t0, linestyle="--", label="seuil détecté")
    ax.legend()
    fig.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def plot_V_before_after_symbolic(df: pd.DataFrame, outpath: Path, drop_frac: float = 0.35, gamma: float = 0.6) -> None:
    # Démo: si perturb_symbolic==1, on réduit S et on pénalise V proportionnellement à la perte de S.
    pert = df["perturb_symbolic"].fillna(0).astype(int)
    S_pert = df["S"] * np.where(pert == 1, 1.0 - drop_frac, 1.0)
    V_pert = df["V"] - gamma * (df["S"] - S_pert)

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(df["t"], df["V"], label="V(t) observé")
    ax.plot(df["t"], V_pert, label="V(t) sous perturbation symbolique")

    # Ligne verticale au premier t perturbé
    idxs = df.index[pert == 1].tolist()
    if idxs:
        t0 = float(df.loc[idxs[0], "t"])
        ax.axvline(t0, linestyle="--", label="début perturbation")

    ax.set_xlabel("t")
    ax.set_ylabel("V(t)")
    ax.set_title("Viabilité avant et après perturbation symbolique")
    ax.legend()
    fig.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--m", type=int, default=3)
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    required = [
        "id","t","O","R","I",
        "survie","energie_nette","integrite","persistance",
        "repertoire","codification","densite_transmission","fidelite",
        "demande_env"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes: {missing}")

    df = df.sort_values(["id", "t"]).reset_index(drop=True)

    w = Weights()
    df["V"] = compute_V(df, w)
    df["S"] = compute_S(df, w)
    df["Cap"] = compute_capacity(df)
    df["Sigma"] = compute_sigma(df)

    # C(t) simplifié, par id
    C_all = []
    for _id, g in df.groupby("id", sort=False):
        g = g.copy()
        g["C"] = compute_C_simplified(g)
        C_all.append(g)
    df = pd.concat(C_all, axis=0).reset_index(drop=True)

    df["delta_C"] = df.groupby("id")["C"].diff().fillna(0.0)

    # Détection seuil sur l'unique id principal, sinon sur la concat
    threshold_idx, thr_value = detect_threshold(df["delta_C"], k=args.k, m=args.m)

    df["threshold_hit"] = 0
    if threshold_idx is not None:
        df.loc[threshold_idx, "threshold_hit"] = 1

    # Exports
    tables_dir = args.outdir / "tables"
    figs_dir = args.outdir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(tables_dir / "processed_synthetic.csv", index=False)

    plot_C_with_threshold(
        df,
        figs_dir / "C_threshold.png",
        threshold_idx=threshold_idx,
        thr_value=thr_value,
    )
    plot_V_before_after_symbolic(
        df,
        figs_dir / "V_symbolic_perturbation.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
