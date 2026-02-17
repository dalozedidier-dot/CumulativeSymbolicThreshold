#!/usr/bin/env python3
"""
ORI-C canonical suite runner.

This script is designed to be an orchestrator, not a new scientific claim.
It produces audit-friendly artifacts:
- processed time series (optional)
- per-run summary table suitable for decision protocol scripts

Usage:
  python 04_Code/pipeline/run_canonical_suite.py --input <csv> --outdir <dir> --n-runs 50 --master-seed 42
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import argparse
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from oric import (
    PreregSpec,
    ExperimentLogger,
    compute_cap_projection,
    compute_sigma,
    compute_viability,
    compute_stock_S,
    compute_order_C,
    detect_s_star_piecewise,
)


def _detect_threshold_delta_C(
    delta_c: pd.Series,
    window_mu: int,
    k: float,
    m: int,
) -> Tuple[bool, Optional[int], float]:
    """Return (hit, first_index, thr_value) using rolling mu and sigma computed on the past."""
    x = delta_c.to_numpy(dtype=float)
    n = len(x)
    if n < window_mu + 2:
        return False, None, float("nan")

    hits = np.zeros(n, dtype=bool)
    thr_last = float("nan")
    for t in range(window_mu + 1, n):
        hist = x[t - window_mu : t]  # past window
        mu = float(np.mean(hist))
        sigma = float(np.std(hist, ddof=0))
        thr = mu + k * sigma
        thr_last = thr
        hits[t] = x[t] > thr

    if m <= 1:
        idx = int(np.argmax(hits)) if hits.any() else None
        return bool(hits.any()), idx, thr_last

    run = 0
    first = None
    for t in range(n):
        if hits[t]:
            run += 1
            if run >= m:
                first = t - m + 1
                break
        else:
            run = 0
    return first is not None, first, thr_last


def process_one_run(
    df: pd.DataFrame,
    prereg: PreregSpec,
    seed: int,
    apply_flags: bool = True,
    noise: float = 0.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = df.copy()

    if noise > 0:
        for col in [
            "O",
            "R",
            "I",
            "survie",
            "energie_nette",
            "integrite",
            "persistance",
            "repertoire",
            "codification",
            "densite_transmission",
            "fidelite",
        ]:
            if col in out.columns:
                out[col] = np.clip(out[col].to_numpy() + rng.normal(0.0, noise, size=len(out)), 0.0, 1.0)

    out["Cap"] = compute_cap_projection(out["O"], out["R"], out["I"], form=prereg.cap_form)
    out["Sigma"] = compute_sigma(out["demande_env"], out["Cap"], form=prereg.sigma_form)
    out["V"] = compute_viability(out, prereg.omega_v)
    out["S"] = compute_stock_S(out, prereg.alpha_s)

    if apply_flags:
        if "perturb_symbolic" in out.columns:
            mask = out["perturb_symbolic"].astype(int).to_numpy() == 1
            if mask.any():
                out.loc[mask, "S"] = out.loc[mask, "S"] * 0.65

        if "cut_symbolic" in out.columns:
            mask = out["cut_symbolic"].astype(int).to_numpy() == 1
            if mask.any():
                out.loc[mask, "S"] = 0.0

    out["C"] = compute_order_C(out)
    out["delta_C"] = out["C"].diff().fillna(0.0)

    hit, first_idx, thr_val = _detect_threshold_delta_C(
        out["delta_C"],
        prereg.window_mu,
        prereg.k_sigma,
        prereg.m_consecutive,
    )
    out["threshold_hit"] = 0
    if hit and first_idx is not None:
        out.loc[first_idx:, "threshold_hit"] = 1
    out.attrs["threshold_any"] = bool(hit)
    out.attrs["threshold_first_index"] = None if first_idx is None else int(first_idx)
    out.attrs["threshold_value_last"] = float(thr_val)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input CSV time series")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--n-runs", type=int, default=50)
    ap.add_argument("--master-seed", type=int, default=42)
    ap.add_argument("--save-processed", action="store_true", help="Save processed CSV per run (can be large)")
    ap.add_argument("--noise", type=float, default=0.0, help="Gaussian noise std applied to selected columns")
    ap.add_argument("--no-flags", action="store_true", help="Do not apply perturb_symbolic and cut_symbolic flags")
    args = ap.parse_args()

    prereg = PreregSpec()
    prereg.validate()

    in_path = Path(args.input)
    outdir = Path(args.outdir)
    tables_dir = outdir / "tables"
    raw_dir = outdir / "raw"
    tables_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    required = [
        "id",
        "t",
        "O",
        "R",
        "I",
        "demande_env",
        "survie",
        "energie_nette",
        "integrite",
        "persistance",
        "repertoire",
        "codification",
        "densite_transmission",
        "fidelite",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    logger = ExperimentLogger(outdir)
    logger.log(
        "run_start",
        {
            "input": str(in_path),
            "n_runs": args.n_runs,
            "master_seed": args.master_seed,
            "prereg": prereg.to_dict(),
        },
    )

    seeds = [args.master_seed + i * 9973 for i in range(args.n_runs)]
    rows = []
    failures = 0

    for run_idx, seed in enumerate(seeds):
        try:
            proc = process_one_run(df, prereg, seed=seed, apply_flags=(not args.no_flags), noise=args.noise)

            s_star_diag = detect_s_star_piecewise(proc["S"].to_numpy(), proc["C"].to_numpy())

            tail = proc.iloc[-prereg.window_W:] if len(proc) >= prereg.window_W else proc
            v_q05 = float(np.quantile(tail["V"].to_numpy(), 0.05))
            a_sigma = float(proc["Sigma"].sum())
            frac_over = float((proc["Sigma"] > 0).mean())
            c_end = float(proc["C"].iloc[-1])
            s_mean = float(proc["S"].mean())

            rows.append(
                {
                    "run_id": run_idx,
                    "seed": seed,
                    "n_steps": int(len(proc)),
                    "V_q05": v_q05,
                    "A_sigma": a_sigma,
                    "frac_over": frac_over,
                    "C_end": c_end,
                    "S_mean": s_mean,
                    "threshold_any": int(bool(proc.attrs.get("threshold_any", False))),
                    "threshold_first_index": proc.attrs.get("threshold_first_index", None),
                    "threshold_value_last": proc.attrs.get("threshold_value_last", float("nan")),
                    "S_star": s_star_diag.get("S_star", float("nan")),
                    "S_star_improvement": s_star_diag.get("improvement", 0.0),
                }
            )

            if args.save_processed:
                proc.to_csv(raw_dir / f"processed_run_{run_idx:04d}.csv", index=False)

            if run_idx == 0:
                proc.to_csv(raw_dir / "processed_example_run_0000.csv", index=False)

        except Exception as e:
            failures += 1
            rows.append({"run_id": run_idx, "seed": seed, "failed": 1, "error": str(e)})

    summary = pd.DataFrame(rows)
    summary_path = tables_dir / "runs_summary.csv"
    summary.to_csv(summary_path, index=False)

    logger.log("run_end", {"failures": failures, "summary_csv": str(summary_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
