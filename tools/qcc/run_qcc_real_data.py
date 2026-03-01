\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass
class QCCParams:
    cmin: float
    ccl_min: float
    mcl: int


def _safe_float_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def load_or_make_demo(data_dir: Path) -> tuple[list[Path], bool]:
    csvs = sorted([p for p in data_dir.glob("*.csv") if p.is_file()])
    if csvs:
        return csvs, False

    # Demo dataset: coherent rotation + decoherence-like drift
    n = 500
    t = np.linspace(0, 20, n)
    # Cq decays from 1 to near 0
    Cq = np.clip(np.exp(-t/6.0), 0, 1)
    # O (noise exposure) ramps up then stabilizes
    O = np.clip(0.15 + 0.25*(1 - np.exp(-t/4.0)), 0, None)
    # R (regulation) starts decent then saturates lower than O
    R = np.clip(0.10 + 0.12*(1 - np.exp(-t/5.0)), 0, None)
    # Optional Ccl rises as Cq drops
    Ccl = np.clip(1 - Cq, 0, 1)

    demo = pd.DataFrame({"t": t, "Cq": Cq, "O": O, "R": R, "Ccl": Ccl})
    demo_path = data_dir / "DEMO_qcc.csv"
    demo.to_csv(demo_path, index=False)
    return [demo_path], True


def compute_sigma(df: pd.DataFrame) -> pd.Series:
    if "t" in df.columns:
        t = _safe_float_series(df["t"])
        if t.isna().all():
            t = pd.Series(np.arange(len(df)), dtype=float)
    else:
        t = pd.Series(np.arange(len(df)), dtype=float)

    # dt: forward difference with last dt repeated
    dt = t.diff().fillna(0.0)
    # If first dt is 0, use median of later diffs when possible
    if len(dt) > 2:
        med = float(np.nanmedian(dt.iloc[1:].to_numpy()))
        if not np.isfinite(med) or med <= 0:
            med = 1.0
        dt.iloc[0] = med
    else:
        dt.iloc[0] = 1.0

    O = _safe_float_series(df["O"]).fillna(0.0).clip(lower=0.0)
    R = _safe_float_series(df["R"]).fillna(0.0).clip(lower=0.0)

    resid = (O - R).clip(lower=0.0)
    sigma = (resid * dt).cumsum()
    return sigma


def detect_tstar(df: pd.DataFrame, params: QCCParams) -> Optional[int]:
    Cq = _safe_float_series(df["Cq"]).fillna(np.nan)
    # First index where Cq < cmin
    mask = Cq < params.cmin
    if not mask.any():
        return None
    return int(mask.idxmax())  # idxmax on bool gives first True


def compute_classical_dominance(df: pd.DataFrame, params: QCCParams) -> Optional[int]:
    if "Ccl" not in df.columns:
        return None
    Ccl = _safe_float_series(df["Ccl"]).fillna(np.nan)
    # Find first index where Ccl stays >= ccl_min for mcl consecutive steps
    ok = (Ccl >= params.ccl_min).to_numpy()
    m = params.mcl
    if len(ok) < m:
        return None
    run = 0
    for i, v in enumerate(ok):
        run = run + 1 if v else 0
        if run >= m:
            return i - m + 1
    return None


def make_overview_plot(out_png: Path, df: pd.DataFrame) -> None:
    # Default colors only
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)

    ax.plot(df["t_plot"], df["Cq_plot"], label="Cq")
    if "Ccl_plot" in df.columns:
        ax.plot(df["t_plot"], df["Ccl_plot"], label="Ccl")
    ax.plot(df["t_plot"], df["O_plot"], label="O")
    ax.plot(df["t_plot"], df["R_plot"], label="R")
    ax.plot(df["t_plot"], df["Sigma_plot"], label="Sigma")

    ax.set_title("QCC overview (measures only)")
    ax.set_xlabel("t")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=140)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=str, required=True)
    ap.add_argument("--out-root", type=str, required=True)
    ap.add_argument("--cmin", type=float, default=0.20)
    ap.add_argument("--ccl-min", type=float, default=0.70)
    ap.add_argument("--mcl", type=int, default=5)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    out_root = Path(args.out_root)
    data_dir.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)

    params = QCCParams(cmin=float(args.cmin), ccl_min=float(args.ccl_min), mcl=int(args.mcl))

    csvs, demo_used = load_or_make_demo(data_dir)

    # Timestamp run folder (stable for CI artifacts)
    from datetime import datetime, timezone
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / f"run_{run_id}"
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    all_events = []

    for p in csvs:
        df = pd.read_csv(p)

        required = {"Cq", "O", "R"}
        missing = sorted(list(required - set(df.columns)))
        if missing:
            raise SystemExit(f"Missing columns in {p.name}: {missing}")

        # t_plot
        if "t" in df.columns:
            t_plot = pd.to_numeric(df["t"], errors="coerce").astype(float)
            if t_plot.isna().all():
                t_plot = pd.Series(np.arange(len(df)), dtype=float)
        else:
            t_plot = pd.Series(np.arange(len(df)), dtype=float)

        sigma = compute_sigma(df)

        tstar_idx = detect_tstar(df, params)
        cdom_idx = compute_classical_dominance(df, params)

        sigma_tstar = float(sigma.iloc[tstar_idx]) if tstar_idx is not None else None
        sigma_cdom = float(sigma.iloc[cdom_idx]) if cdom_idx is not None else None

        # Prepare output table
        out = pd.DataFrame({
            "t": t_plot,
            "Cq": pd.to_numeric(df["Cq"], errors="coerce").astype(float),
            "O": pd.to_numeric(df["O"], errors="coerce").astype(float),
            "R": pd.to_numeric(df["R"], errors="coerce").astype(float),
            "Sigma": sigma.astype(float),
        })
        if "Ccl" in df.columns:
            out["Ccl"] = pd.to_numeric(df["Ccl"], errors="coerce").astype(float)

        # Normalized columns for plot only
        out["t_plot"] = out["t"]
        out["Cq_plot"] = out["Cq"].clip(0, 1)
        out["O_plot"] = out["O"].clip(lower=0)
        out["R_plot"] = out["R"].clip(lower=0)
        out["Sigma_plot"] = out["Sigma"].clip(lower=0)
        if "Ccl" in out.columns:
            out["Ccl_plot"] = out["Ccl"].clip(0, 1)

        run_tag = p.stem
        out_csv = tables_dir / f"timeseries_out_{run_tag}.csv"
        out.to_csv(out_csv, index=False)

        all_events.append({
            "run": run_tag,
            "tstar_index": tstar_idx,
            "tstar_t": float(out["t"].iloc[tstar_idx]) if tstar_idx is not None else None,
            "sigma_at_tstar": sigma_tstar,
            "cdom_index": cdom_idx,
            "cdom_t": float(out["t"].iloc[cdom_idx]) if cdom_idx is not None else None,
            "sigma_at_cdom": sigma_cdom,
        })

        plot_png = figs_dir / f"qcc_overview_{run_tag}.png"
        make_overview_plot(plot_png, out)

    # Calibrate S* if we have at least one sigma_at_tstar
    sigmas = [e["sigma_at_tstar"] for e in all_events if e["sigma_at_tstar"] is not None]
    S_star = float(np.median(sigmas)) if sigmas else None

    events_csv = tables_dir / "events.csv"
    pd.DataFrame(all_events).to_csv(events_csv, index=False)

    summary = {
        "demo_used": bool(demo_used),
        "params": {"C_min": params.cmin, "Ccl_min": params.ccl_min, "m_cl": params.mcl},
        "runs": [e["run"] for e in all_events],
        "S_star_median": S_star,
        "n_tstar": int(len(sigmas)),
    }
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    # Manifest
    from tools.qcc.make_manifest import write_manifest
    write_manifest(run_dir, run_dir / "manifest.json")

    print(f"QCC run written to: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
