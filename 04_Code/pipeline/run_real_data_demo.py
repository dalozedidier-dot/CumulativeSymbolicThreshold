#!/usr/bin/env python3
"""04_Code/pipeline/run_real_data_demo.py

Minimal real-data pipeline for ORI-C variables.

Input
- CSV with at least O, R, I in [0,1].
- Optional: demand column. If missing, demand is approximated as 0.90 * Cap.

This script is deliberately conservative.
- It does not guess semantic proxies.
- It only computes the ORI-C variables from provided series.

Outputs
- <outdir>/tables/real_timeseries_oric.csv
- <outdir>/tables/summary.json
- <outdir>/figures/svc_real.png

Example
python 04_Code/pipeline/run_real_data_demo.py \
  --input 03_Data/real/example.csv \
  --outdir 05_Results/real/example_run \
  --col-O O --col-R R --col-I I --col-demand demand
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _detect_threshold(delta_C: np.ndarray, k: float, m: int, baseline_n: int) -> tuple[int | None, float]:
    x = np.asarray(delta_C, dtype=float)
    n = int(len(x))
    if n == 0:
        return None, 0.0

    bn = int(baseline_n)
    if bn < 5:
        bn = 5
    bn = min(bn, n)

    base = x[:bn]
    mu = float(np.mean(base))
    sd = float(np.std(base))
    thr = mu + float(k) * sd

    consec = 0
    for i in range(n):
        if float(x[i]) > thr:
            consec += 1
            if consec >= int(m):
                return int(i), float(thr)
        else:
            consec = 0

    return None, float(thr)


def compute_oric_from_real(
    df: pd.DataFrame,
    *,
    col_O: str,
    col_R: str,
    col_I: str,
    col_demand: str | None,
    cap_scale: float,
    auto_scale: bool,
    sigma_star: float,
    sigma_to_S_alpha: float,
    S_decay: float,
    C_beta: float,
    C_gamma: float,
    k: float,
    m: int,
    baseline_n: int,
) -> tuple[pd.DataFrame, dict]:
    out = df.copy()

    if "t" not in out.columns:
        out["t"] = np.arange(len(out), dtype=int)

    O = pd.to_numeric(out[col_O], errors="coerce").astype(float)
    R = pd.to_numeric(out[col_R], errors="coerce").astype(float)
    I = pd.to_numeric(out[col_I], errors="coerce").astype(float)

    O = O.clip(0.0, 1.0)
    R = R.clip(0.0, 1.0)
    I = I.clip(0.0, 1.0)

    # scale Cap
    base_cap = (O * R * I).astype(float)

    if col_demand is not None and col_demand in out.columns:
        demand_raw = pd.to_numeric(out[col_demand], errors="coerce").astype(float)
        if auto_scale:
            denom = float(np.nanmedian(base_cap))
            numer = float(np.nanmedian(demand_raw))
            if denom > 1e-9 and np.isfinite(numer):
                cap_scale_eff = numer / (0.90 * denom)
            else:
                cap_scale_eff = cap_scale
        else:
            cap_scale_eff = cap_scale
        demand = demand_raw
    else:
        cap_scale_eff = cap_scale
        demand = 0.90 * base_cap * cap_scale_eff

    Cap = base_cap * float(cap_scale_eff)

    Sigma = np.maximum(0.0, demand - Cap)
    Sigma_symbolic = np.maximum(0.0, Sigma - float(sigma_star))

    # integrate S and C over time
    S = np.zeros(len(out), dtype=float)
    C = np.zeros(len(out), dtype=float)

    S0 = 0.20
    if "S0" in out.columns:
        try:
            S0 = float(out["S0"].iloc[0])
        except Exception:
            S0 = 0.20

    s_prev = float(np.clip(S0, 0.0, 1.0))
    c_prev = 0.0

    for i in range(len(out)):
        s_prev = float(np.clip(s_prev + sigma_to_S_alpha * float(Sigma_symbolic[i]) - float(S_decay) * s_prev, 0.0, 1.0))
        mismatch_frac = float(Sigma[i] / (Cap.iloc[i] + 1e-9)) if isinstance(Cap, pd.Series) else float(Sigma[i] / (Cap[i] + 1e-9))
        V = float(np.clip(1.0 - 1.2 * mismatch_frac, 0.0, 1.0))
        c_prev = float(c_prev + float(C_beta) * s_prev - float(C_gamma) * V)

        S[i] = s_prev
        C[i] = c_prev

    out["O"] = O
    out["R"] = R
    out["I"] = I
    out["Cap"] = Cap
    out["demand"] = demand
    out["Sigma"] = Sigma
    out["S"] = S

    # recompute V as series
    mismatch_frac = Sigma / (Cap + 1e-9)
    out["V"] = np.clip(1.0 - 1.2 * mismatch_frac, 0.0, 1.0)
    out["C"] = C
    out["delta_C"] = out["C"].diff().fillna(0.0)

    thr_idx, thr_val = _detect_threshold(out["delta_C"].to_numpy(dtype=float), k=float(k), m=int(m), baseline_n=int(baseline_n))
    out["threshold_value"] = float(thr_val)
    out["threshold_hit"] = 0
    if thr_idx is not None:
        out.loc[int(thr_idx), "threshold_hit"] = 1

    summary = {
        "cap_scale_used": float(cap_scale_eff),
        "threshold_hit_t": None if thr_idx is None else int(out.loc[int(thr_idx), "t"]),
        "threshold_value": float(thr_val),
        "C_end": float(out["C"].iloc[-1]),
        "S_end": float(out["S"].iloc[-1]),
        "Sigma_sum": float(out["Sigma"].sum()),
    }

    return out, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)

    ap.add_argument("--col-O", default="O")
    ap.add_argument("--col-R", default="R")
    ap.add_argument("--col-I", default="I")
    ap.add_argument("--col-demand", default="demand")

    ap.add_argument("--cap-scale", type=float, default=1000.0)
    ap.add_argument("--auto-scale", action="store_true", help="If demand provided, auto-fit cap_scale")

    ap.add_argument("--sigma-star", type=float, default=0.0)
    ap.add_argument("--sigma-to-s-alpha", type=float, default=0.0008)
    ap.add_argument("--tau", type=float, default=0.0)
    ap.add_argument("--s-decay", type=float, default=0.002)

    ap.add_argument("--C-beta", type=float, default=0.40)
    ap.add_argument("--C-gamma", type=float, default=0.12)

    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)

    args = ap.parse_args()

    outdir = Path(args.outdir)
    tabdir = outdir / "tables"
    figdir = outdir / "figures"
    tabdir.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(Path(args.input))

    col_demand = str(args.col_demand) if str(args.col_demand).strip() else None
    if col_demand is not None and col_demand not in df.columns:
        col_demand = None

    if float(args.tau) > 0.0:
        s_decay = 1.0 / float(args.tau)
    else:
        s_decay = float(args.s_decay)

    out, summary = compute_oric_from_real(
        df,
        col_O=str(args.col_O),
        col_R=str(args.col_R),
        col_I=str(args.col_I),
        col_demand=col_demand,
        cap_scale=float(args.cap_scale),
        auto_scale=bool(args.auto_scale),
        sigma_star=float(args.sigma_star),
        sigma_to_S_alpha=float(args.sigma_to_s_alpha),
        S_decay=float(s_decay),
        C_beta=float(args.C_beta),
        C_gamma=float(args.C_gamma),
        k=float(args.k),
        m=int(args.m),
        baseline_n=int(args.baseline_n),
    )

    out.to_csv(tabdir / "real_timeseries_oric.csv", index=False)
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # one compact figure
    plt.figure(figsize=(10, 6))
    plt.plot(out["t"], out["S"], label="S")
    plt.plot(out["t"], out["V"], label="V")
    plt.plot(out["t"], out["C"], label="C")
    if bool((out["threshold_hit"] > 0).any()):
        idx = int(out.index[out["threshold_hit"] > 0][0])
        plt.axvline(x=float(out.loc[idx, "t"]), linestyle=":", label="threshold_hit")
    plt.xlabel("t")
    plt.title("ORI-C variables from real data")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figdir / "svc_real.png", dpi=160)
    plt.close()

    print(json.dumps({"outdir": str(outdir), "threshold_hit_t": summary.get("threshold_hit_t")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
