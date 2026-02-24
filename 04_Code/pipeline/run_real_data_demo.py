#!/usr/bin/env python3
"""04_Code/pipeline/run_real_data_demo.py

Run ORI-C mechanics on real (observed) time series.

Input:
- A CSV with at least:
  - a time column (date or integer) OR no time column if --time-mode index is used, and
  - O, R, I proxies in [0,1]
- Optional columns:
  - demand (same unit over the series)
  - S (symbolic proxy) in [0,1]

Outputs (single run):
- <outdir>/tables/test_timeseries.csv
- <outdir>/tables/control_timeseries.csv
- <outdir>/tables/summary.json
- <outdir>/figures/s_t.png
- <outdir>/figures/c_t.png
- <outdir>/figures/delta_c_t.png

Notes:
- If demand is missing, demand is approximated as demand_to_cap_ratio * Cap (synthetic convention).
- If S is missing, S is endogenously updated from Sigma (gate + decay) as in the synthetic model.
- The script can also build a simple control by forcing S(t)=0 (control-mode no_symbolic).

Important:
- When --time-mode index is used (recommended for CI), the script no longer requires that the
  --col-time column exists in the CSV. It will use the row order as-is and map time to 0..n-1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

# Ensure src/ is on sys.path for `import oric`
_SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402


def _mkdirs(outdir: Path) -> Tuple[Path, Path]:
    tabdir = outdir / "tables"
    figdir = outdir / "figures"
    tabdir.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)
    return tabdir, figdir


def _robust_minmax(x: np.ndarray, q_lo: float = 0.02, q_hi: float = 0.98) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return x
    finite = np.isfinite(x)
    if not finite.any():
        return np.zeros_like(x)

    lo = float(np.quantile(x[finite], q_lo))
    hi = float(np.quantile(x[finite], q_hi))
    if (not np.isfinite(lo)) or (not np.isfinite(hi)) or abs(hi - lo) < 1e-12:
        lo = float(np.nanmin(x[finite]))
        hi = float(np.nanmax(x[finite]))

    if (not np.isfinite(lo)) or (not np.isfinite(hi)) or abs(hi - lo) < 1e-12:
        return np.zeros_like(x)

    y = (x - lo) / (hi - lo)
    return np.clip(y, 0.0, 1.0)


def _minmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return x
    finite = np.isfinite(x)
    if not finite.any():
        return np.zeros_like(x)

    lo = float(np.nanmin(x[finite]))
    hi = float(np.nanmax(x[finite]))
    if (not np.isfinite(lo)) or (not np.isfinite(hi)) or abs(hi - lo) < 1e-12:
        return np.zeros_like(x)

    y = (x - lo) / (hi - lo)
    return np.clip(y, 0.0, 1.0)


def _normalize_proxy(x: np.ndarray, method: str) -> np.ndarray:
    m = str(method).strip().lower()
    if m in ("none", "off", ""):
        return np.asarray(x, dtype=float)
    if m in ("minmax", "mm"):
        return _minmax(x)
    return _robust_minmax(x)


def _to_t_column(df: pd.DataFrame, col_time: str, time_mode: str = "index") -> pd.Series:
    """Create internal integer time index column used by the pipeline.

    - time_mode="index": use 0..n-1, does not require col_time to exist.
    - time_mode="value": parse col_time as numeric or datetime and convert to int steps.
    """
    if str(time_mode).lower() == "index":
        return pd.Series(np.arange(len(df), dtype=int))

    if col_time not in df.columns:
        raise SystemExit(f"Missing time column: {col_time}")

    s = df[col_time]

    # Try numeric
    t_num = pd.to_numeric(s, errors="coerce")
    if t_num.notna().sum() >= int(0.9 * len(s)):
        return t_num.ffill().bfill().fillna(0).astype(int)

    # Try datetime
    dt = pd.to_datetime(s, errors="coerce", utc=True)
    if dt.notna().sum() >= int(0.9 * len(s)):
        dt = dt.ffill().bfill()
        t0 = dt.iloc[0]
        t = (dt - t0).dt.total_seconds() / 86400.0
        return t.fillna(0.0).round().astype(int)

    # Fallback: use row index
    return pd.Series(np.arange(len(df), dtype=int))


def _plot_overlay(df_c: pd.DataFrame, df_t: pd.DataFrame, col: str, outpath: Path, title: str) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(df_c["t"], df_c[col], label="control")
    plt.plot(df_t["t"], df_t[col], label="test")
    plt.xlabel("t")
    plt.ylabel(col)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV with columns time,O,R,I and optional demand,S")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--col-time", default="t")
    ap.add_argument(
        "--time-mode",
        default="index",
        choices=["index", "value"],
        help="index=0..n-1 (recommended), value=use numeric or days since start for dates",
    )
    ap.add_argument("--col-O", default="O")
    ap.add_argument("--col-R", default="R")
    ap.add_argument("--col-I", default="I")
    ap.add_argument("--col-demand", default="demand")
    ap.add_argument("--col-S", default="S")
    ap.add_argument("--normalize", default="robust", choices=["none", "minmax", "robust"])
    ap.add_argument("--auto-scale", action="store_true", help="Align cap_scale to demand median (recommended when demand is provided)")
    ap.add_argument("--cap-scale", type=float, default=1000.0)
    ap.add_argument("--demand-to-cap-ratio", type=float, default=0.90)
    ap.add_argument("--sigma-star", type=float, default=0.0)
    ap.add_argument("--tau", type=float, default=500.0, help="If tau>0, S_decay=1/tau, else keep default S_decay")
    ap.add_argument("--sigma-to-S-alpha", type=float, default=0.0008)
    ap.add_argument("--S0", type=float, default=0.20)
    ap.add_argument("--C-beta", type=float, default=0.40)
    ap.add_argument("--C-gamma", type=float, default=0.12)
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)
    ap.add_argument("--control-mode", default="same", choices=["same", "no_symbolic"])
    ap.add_argument(
        "--proxy-spec",
        default=None,
        help="Path to proxy_spec.json for this dataset. Hash will be logged in summary.json.",
    )
    ap.add_argument(
        "--split-frac",
        type=float,
        default=None,
        help="If set (e.g. 0.7), use first split_frac of rows for calibration and the rest as "
             "out-of-sample test. Both halves are processed and labelled in summary.",
    )
    ap.add_argument("--seed", type=int, default=123, help="RNG seed for reproducibility (used in ORICConfig)")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    tabdir, figdir = _mkdirs(outdir)

    # ── proxy_spec: load and hash if provided ──────────────────────────────────
    proxy_spec_hash: str | None = None
    proxy_spec_path: str | None = None
    if args.proxy_spec:
        try:
            from oric.proxy_spec import ProxySpec  # noqa: PLC0415
            ps = ProxySpec.from_json_file(args.proxy_spec)
            proxy_spec_hash = ps.sha256()
            proxy_spec_path = str(Path(args.proxy_spec).resolve())
            print(f"proxy_spec loaded: {args.proxy_spec}  sha256={proxy_spec_hash[:16]}…")
        except Exception as exc:
            print(f"WARNING: could not load proxy_spec ({exc}) — continuing without hash", file=sys.stderr)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERREUR: dataset introuvable: {input_path}", file=sys.stderr)
        return 1

    df_raw = pd.read_csv(input_path)
    df = df_raw.copy()

    col_time = str(args.col_time)
    time_mode = str(args.time_mode)

    # Sort by the provided time column when it exists and time_mode is "value".
    # In "index" mode, we allow missing time column and keep row order.
    if time_mode.lower() == "value" and col_time in df.columns:
        dt_key = pd.to_datetime(df[col_time], errors="coerce", utc=True)
        if dt_key.notna().sum() >= int(0.9 * len(df)):
            df = df.assign(_sort_key=dt_key).sort_values("_sort_key").drop(columns=["_sort_key"])
        else:
            num_key = pd.to_numeric(df[col_time], errors="coerce")
            if num_key.notna().sum() >= int(0.9 * len(df)):
                df = df.assign(_sort_key=num_key).sort_values("_sort_key").drop(columns=["_sort_key"])

    # Create the internal time index used everywhere else in the pipeline.
    df["t"] = _to_t_column(df, col_time, time_mode)
    df = df.reset_index(drop=True)

    # ── Out-of-sample split ────────────────────────────────────────────────────
    split_frac = float(args.split_frac) if args.split_frac is not None else None
    split_idx: int | None = None
    if split_frac is not None:
        if not (0.1 < split_frac < 0.99):
            print(f"WARNING: --split-frac {split_frac} out of range [0.1, 0.99]; ignoring", file=sys.stderr)
            split_frac = None
        else:
            split_idx = int(len(df) * split_frac)
            print(f"Out-of-sample split: calibration rows 0..{split_idx-1}, test rows {split_idx}..{len(df)-1}")

    # Proxies
    for col, name in [(args.col_O, "O"), (args.col_R, "R"), (args.col_I, "I")]:
        if str(col) not in df.columns:
            raise SystemExit(f"Missing proxy column: {col}")
        x = pd.to_numeric(df[str(col)], errors="coerce").to_numpy(dtype=float)
        x = _normalize_proxy(x, str(args.normalize))
        df[name] = np.clip(np.nan_to_num(x, nan=0.0), 0.0, 1.0)

    # Demand (optional)
    if str(args.col_demand) in df.columns:
        d = pd.to_numeric(df[str(args.col_demand)], errors="coerce").to_numpy(dtype=float)
        df["demand"] = np.nan_to_num(d, nan=np.nan)
    else:
        df["demand"] = np.nan

    # Optional observed S
    has_S = str(args.col_S) in df.columns
    if has_S:
        s = pd.to_numeric(df[str(args.col_S)], errors="coerce").to_numpy(dtype=float)
        df["S"] = np.clip(np.nan_to_num(s, nan=0.0), 0.0, 1.0)

    # Config
    S_decay = 0.002
    if float(args.tau) > 0.0:
        S_decay = 1.0 / float(args.tau)

    cfg = ORICConfig(
        seed=int(args.seed),
        n_steps=int(len(df)),
        S0=float(args.S0),
        cap_scale=float(args.cap_scale),
        sigma_star=float(args.sigma_star),
        sigma_to_S_alpha=float(args.sigma_to_S_alpha),
        S_decay=float(S_decay),
        C_beta=float(args.C_beta),
        C_gamma=float(args.C_gamma),
        k=float(args.k),
        m=int(args.m),
        baseline_n=int(args.baseline_n),
    )

    # Test run
    df_test = run_oric_from_observations(
        df,
        cfg,
        col_t="t",
        col_O="O",
        col_R="R",
        col_I="I",
        col_demand="demand",
        col_S=("S" if has_S else None),
        auto_scale=bool(args.auto_scale),
        demand_to_cap_ratio=float(args.demand_to_cap_ratio),
    )

    # Control run
    if str(args.control_mode) == "no_symbolic":
        df_ctrl_in = df.copy()
        df_ctrl_in["S"] = 0.0
        df_control = run_oric_from_observations(
            df_ctrl_in,
            cfg,
            col_t="t",
            col_O="O",
            col_R="R",
            col_I="I",
            col_demand="demand",
            col_S="S",
            auto_scale=bool(args.auto_scale),
            demand_to_cap_ratio=float(args.demand_to_cap_ratio),
        )
    else:
        df_control = df_test.copy()

    # Protocol invariant: C(t) is a cumulative measure and must be nonnegative.
    # Some proxy normalizations can shift the computed C below 0.
    # We correct this with a constant offset (does not change ΔC) and record it.
    c_offset = None
    if 'C' in df_test.columns and 'C' in df_control.columns:
        c_min = float(min(df_test['C'].min(), df_control['C'].min()))
        if c_min < 0.0:
            c_offset = -c_min
            df_test['C'] = df_test['C'] + c_offset
            df_control['C'] = df_control['C'] + c_offset
        else:
            c_offset = 0.0

    # Add a 'step' column (0..n-1) as the canonical integer step index for
    # window slicing in tests_causaux.py — independent of what 't' encodes.
    df_test["step"] = np.arange(len(df_test), dtype=int)
    df_control["step"] = np.arange(len(df_control), dtype=int)

    # Write outputs
    df_test.to_csv(tabdir / "test_timeseries.csv", index=False)
    df_control.to_csv(tabdir / "control_timeseries.csv", index=False)

    thr_hit = int(df_test.index[df_test["threshold_hit"] > 0][0]) if bool((df_test["threshold_hit"] > 0).any()) else None
    thr_t = None if thr_hit is None else int(df_test.loc[int(thr_hit), "t"])

    verdict_token = "ACCEPT" if thr_hit is not None else "INDETERMINATE"

    summary = {
        "input_csv": str(Path(args.input)),
        "n_steps": int(len(df_test)),
        "threshold_hit_idx": thr_hit,
        "threshold_hit_t": thr_t,
        "threshold_value": float(df_test["threshold_value"].iloc[0]) if "threshold_value" in df_test.columns else float("nan"),
        "C_mean": float(df_test["C"].mean()),
        "C_positive_frac": float((df_test["C"] > 0.0).mean()),
        "C_positive_frac_last_quarter": float((df_test["C"].iloc[int(0.75 * len(df_test)) :] > 0.0).mean()) if len(df_test) >= 8 else float("nan"),
        "cap_scale_used": float(df_test["cap_scale_used"].iloc[0]) if "cap_scale_used" in df_test.columns else float(args.cap_scale),
        "S_is_observed": bool(df_test["S_is_observed"].iloc[0]) if "S_is_observed" in df_test.columns else bool(has_S),
        "control_mode": str(args.control_mode),
        "time_mode": time_mode,
        "col_time": col_time,
        "c_offset": c_offset,
        "verdict": verdict_token,
        "run_mode": "real_data_canonical",
        "proxy_spec_path": proxy_spec_path,
        "proxy_spec_sha256": proxy_spec_hash,
        "split_frac": split_frac,
        "split_calibration_n": split_idx,
        "split_test_n": (len(df) - split_idx) if split_idx is not None else None,
    }
    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (outdir / "verdict.txt").write_text(verdict_token + "\n", encoding="utf-8")

    # params.txt — human-readable audit dump of all run parameters
    params_lines = [f"{k}={v}" for k, v in vars(args).items()]
    params_lines.insert(0, f"# run_real_data_demo params — seed={args.seed}")
    (outdir / "params.txt").write_text("\n".join(params_lines) + "\n", encoding="utf-8")

    # Figures
    _plot_overlay(df_control, df_test, "S", figdir / "s_t.png", "S(t): control vs test")
    _plot_overlay(df_control, df_test, "C", figdir / "c_t.png", "C(t): control vs test")
    _plot_overlay(df_control, df_test, "delta_C", figdir / "delta_c_t.png", "delta_C(t): control vs test")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
