#!/usr/bin/env python3
"""
Exécute une suite minimale ORI-C pour produire des runs indépendants (seeds) utilisables
par les règles de décision (alpha, SESOI, gate, verdicts).

Sorties
- <outdir>/tables/oric_suite_runs.csv : 1 ligne par run (seed)
- <outdir>/tables/oric_suite_summary.csv : agrégats descriptifs par condition
- <outdir>/manifest.json : paramètres de la suite

Usage
python 04_Code/pipeline/run_oric_suite.py --outdir 05_Results/oric_suite --replicates 50
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, replace
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ori_c_pipeline import ORICConfig, run_oric


def _maybe_tqdm(iterable, enabled: bool):
    if not enabled:
        return iterable
    try:
        from tqdm import tqdm  # type: ignore
        return tqdm(iterable)
    except Exception:
        return iterable


def summarize_run(df: pd.DataFrame, window: int) -> Dict[str, Any]:
    if len(df) < window:
        window = max(1, len(df))
    tail = df.tail(window)

    return {
        "n_steps": int(len(df)),
        "Cap_mean": float(df["Cap"].mean()),
        "Cap_end": float(df["Cap"].iloc[-1]),
        "A_Sigma": float(df["Sigma"].sum()),
        "frac_over": float((df["Sigma"] > 0.0).mean()),
        "V_q05_post": float(tail["V"].quantile(0.05)),
        "V_mean_post": float(tail["V"].mean()),
        "C_end": float(df["C"].iloc[-1]),
        "C_median_post": float(tail["C"].median()),
        "threshold_any": int((df["threshold_hit"] > 0).any()),
    }


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="05_Results/oric_suite")
    ap.add_argument("--replicates", type=int, default=50)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--window", type=int, default=20)
    ap.add_argument("--n-steps", type=int, default=120)
    ap.add_argument("--progress", action="store_true")
    args = ap.parse_args()

    outdir = args.outdir
    tables_dir = os.path.join(outdir, "tables")
    ensure_dir(tables_dir)

    base_cfg = ORICConfig(n_steps=args.n_steps)

    rows: List[Dict[str, Any]] = []
    seed = args.seed_base

    # Suite: T1 (factoriel ORI), T3 (overload), T4 (S rich vs poor), T7 (symbolic cut)
    # T1: 2 niveaux pour limiter la taille et rester exécutable rapidement.
    levels = {"low": 0.55, "high": 0.90}
    for o_label, o_val in levels.items():
        for r_label, r_val in levels.items():
            for i_label, i_val in levels.items():
                condition = f"T1_ORI_{o_label}_{r_label}_{i_label}"
                cfg_template = replace(base_cfg, init_O=o_val, init_R=r_val, init_I=i_val, intervention="none")
                for _ in _maybe_tqdm(range(args.replicates), enabled=args.progress):
                    cfg = replace(cfg_template, seed=seed)
                    df = run_oric(cfg)
                    s = summarize_run(df, window=args.window)
                    rows.append({**s, "test_id": "T1", "condition": condition, "seed": seed, **asdict(cfg)})
                    seed += 1

    # T3: surcharge de demande via demand_shock avec différents demand_extra
    overloads = [0.00, 0.10, 0.20, 0.30, 0.40]
    for extra in overloads:
        condition = f"T3_overload_{extra:.2f}"
        if extra == 0.0:
            cfg_template = replace(base_cfg, intervention="none")
        else:
            cfg_template = replace(
                base_cfg,
                intervention="demand_shock",
                intervention_point=60,
                demand_extra=float(extra),
            )
        for _ in _maybe_tqdm(range(args.replicates), enabled=args.progress):
            cfg = replace(cfg_template, seed=seed)
            df = run_oric(cfg)
            s = summarize_run(df, window=args.window)
            rows.append({**s, "test_id": "T3", "condition": condition, "seed": seed, **asdict(cfg)})
            seed += 1

    # T4: S rich vs poor, ORI identiques
    rich_cfg = replace(base_cfg, alpha_sigma_to_S=0.12, S_decay=0.015, S_floor=0.06, beta_S_to_C=0.08)
    poor_cfg = replace(base_cfg, alpha_sigma_to_S=0.05, S_decay=0.030, S_floor=0.01, beta_S_to_C=0.05)

    for label, cfg_template in [("rich", rich_cfg), ("poor", poor_cfg)]:
        condition = f"T4_S_{label}"
        cfg_template = replace(cfg_template, intervention="none")
        for _ in _maybe_tqdm(range(args.replicates), enabled=args.progress):
            cfg = replace(cfg_template, seed=seed)
            df = run_oric(cfg)
            s = summarize_run(df, window=args.window)
            rows.append({**s, "test_id": "T4", "condition": condition, "seed": seed, **asdict(cfg)})
            seed += 1

    # T7: coupure symbolique, comparaison implicite contre rich sans coupure
    cut_cfg = replace(
        rich_cfg,
        intervention="symbolic_cut",
        intervention_point=60,
    )
    condition = "T7_S_cut"
    for _ in _maybe_tqdm(range(args.replicates), enabled=args.progress):
        cfg = replace(cut_cfg, seed=seed)
        df = run_oric(cfg)
        s = summarize_run(df, window=args.window)
        rows.append({**s, "test_id": "T7", "condition": condition, "seed": seed, **asdict(cfg)})
        seed += 1

    df_runs = pd.DataFrame(rows)
    runs_path = os.path.join(tables_dir, "oric_suite_runs.csv")
    df_runs.to_csv(runs_path, index=False)

    # Summary table
    summary = (
        df_runs.groupby(["test_id", "condition"], dropna=False)
        .agg(
            N=("seed", "count"),
            Cap_mean_mean=("Cap_mean", "mean"),
            V_q05_post_mean=("V_q05_post", "mean"),
            C_end_mean=("C_end", "mean"),
            A_Sigma_mean=("A_Sigma", "mean"),
            threshold_rate=("threshold_any", "mean"),
        )
        .reset_index()
    )
    summary_path = os.path.join(tables_dir, "oric_suite_summary.csv")
    summary.to_csv(summary_path, index=False)

    manifest = {
        "outdir": outdir,
        "replicates": args.replicates,
        "seed_base": args.seed_base,
        "window": args.window,
        "n_steps": args.n_steps,
        "suite": ["T1_factorial_2x2x2", "T3_overload", "T4_S_rich_vs_poor", "T7_symbolic_cut"],
    }
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote: {runs_path}")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
