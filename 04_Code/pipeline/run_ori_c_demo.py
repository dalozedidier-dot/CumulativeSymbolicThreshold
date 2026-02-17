"""
Démo ORI-C (Option B).

Produit:
- figures/01_evolution_C_seuil.png
- figures/02_effet_intervention.png
- tables/oric_control.csv
- tables/oric_intervention.csv
- tables/oric_summary.csv
"""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

import matplotlib.pyplot as plt
import pandas as pd

# Allow direct execution from repo root: python 04_Code/pipeline/run_ori_c_demo.py
ROOT = Path(__file__).resolve().parents[1]  # 04_Code
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.ori_c_pipeline import ORICConfig, run_oric  # noqa: E402


def _plot_C(df: pd.DataFrame, outpath: Path, title: str) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    ax.plot(df["t"], df["C"], label="C(t)")
    hits = df.index[df["threshold_hit"] == 1].tolist()
    if hits:
        ax.scatter(df.loc[hits, "t"], df.loc[hits, "C"], label="seuil détecté")

    ax.set_xlabel("t")
    ax.set_ylabel("C(t)")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def _plot_V(df_control: pd.DataFrame, df_int: pd.DataFrame, outpath: Path, intervention_point: int) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    ax.plot(df_control["t"], df_control["V"], label="contrôle")
    ax.plot(df_int["t"], df_int["V"], label="intervention")
    ax.axvline(float(intervention_point), linestyle="--", label="début intervention")

    ax.set_xlabel("t")
    ax.set_ylabel("V(t)")
    ax.set_title("Effet d'une intervention sur V(t)")
    ax.legend()
    fig.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-steps", type=int, default=100)
    ap.add_argument("--intervention", type=str, default="symbolic_cut", choices=["symbolic_cut", "demand_shock", "capacity_hit"])
    ap.add_argument("--intervention-point", type=int, default=70)
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--window", type=int, default=10)
    args = ap.parse_args()

    outdir = args.outdir
    figs = outdir / "figures"
    tables = outdir / "tables"
    figs.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    cfg_control = ORICConfig(
        seed=args.seed,
        n_steps=args.n_steps,
        intervention="none",
        intervention_point=args.intervention_point,
        k=args.k,
        m=args.m,
        window=args.window,
    )
    cfg_int = ORICConfig(
        seed=args.seed,
        n_steps=args.n_steps,
        intervention=args.intervention,
        intervention_point=args.intervention_point,
        k=args.k,
        m=args.m,
        window=args.window,
    )

    df_control = run_oric(cfg_control)
    df_int = run_oric(cfg_int)

    df_control.to_csv(tables / "oric_control.csv", index=False)
    df_int.to_csv(tables / "oric_intervention.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "scenario": "control",
                "V_mean_pre": float(df_control[df_control["t"] < args.intervention_point]["V"].mean()),
                "V_mean_post": float(df_control[df_control["t"] > args.intervention_point + 10]["V"].mean()),
                "C_end": float(df_control["C"].iloc[-1]),
                "threshold_hits": int(df_control["threshold_hit"].sum()),
            },
            {
                "scenario": args.intervention,
                "V_mean_pre": float(df_int[df_int["t"] < args.intervention_point]["V"].mean()),
                "V_mean_post": float(df_int[df_int["t"] > args.intervention_point + 10]["V"].mean()),
                "C_end": float(df_int["C"].iloc[-1]),
                "threshold_hits": int(df_int["threshold_hit"].sum()),
            },
        ]
    )
    summary.to_csv(tables / "oric_summary.csv", index=False)

    _plot_C(df_control, figs / "01_evolution_C_seuil.png", "C(t) et détection de seuil, contrôle")
    _plot_V(df_control, df_int, figs / "02_effet_intervention.png", args.intervention_point)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
