# tools/qcc_real_data_from_runs_index.py
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from make_manifest import write_manifest_sha256


@dataclass
class RunRow:
    run_id: str
    cq_csv: str
    time_col: str
    cq_col: str
    spectrum_csv: str
    u_imp: Optional[float]
    o_method: str
    o_fmin: Optional[float]
    o_fmax: Optional[float]
    r_definition: str
    r_value: float
    mode: str
    notes: str


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _read_mapping(mapping_path: Path) -> Dict[str, Any]:
    return json.loads(mapping_path.read_text(encoding="utf-8"))


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, float) and math.isnan(x):
            return None
        return float(x)
    except Exception:
        return None


def _require_time_strict(df: pd.DataFrame, time_col: str) -> None:
    t = df[time_col].to_numpy(dtype=float)
    if len(t) < 2:
        return
    dt = np.diff(t)
    if not np.all(dt > 0):
        bad = int(np.sum(dt <= 0))
        raise SystemExit(f"Time is not strictly increasing ({bad} invalid steps) in {time_col}.")


def _compute_sigma_constant_o(df: pd.DataFrame, time_col: str, o_val: float, r_val: float) -> pd.Series:
    t = df[time_col].to_numpy(dtype=float)
    if len(t) < 2:
        return pd.Series(np.zeros(len(t)), index=df.index)
    dt = np.diff(t)
    dt = np.where(dt > 0, dt, 0.0)
    resid = max(0.0, float(o_val) - float(r_val))
    sigma = np.zeros_like(t, dtype=float)
    for k in range(1, len(t)):
        sigma[k] = sigma[k - 1] + resid * dt[k - 1]
    return pd.Series(sigma, index=df.index)


def _bandpower_from_spectrum(
    spectrum_csv: Path,
    u_imp_target: float,
    fmin: float,
    fmax: float,
    max_abs_delta_allowed: float,
) -> Tuple[float, float, float, float]:
    """
    Returns (O, u_imp_used, fmin_used, fmax_used).

    Spectrum CSV format expected:
      - U_imp (repeated blocks)
      - Frequency
      - Amplitude
    """
    sdf = pd.read_csv(spectrum_csv)

    required = {"U_imp", "Frequency", "Amplitude"}
    if not required.issubset(set(sdf.columns)):
        raise SystemExit(f"Spectrum file {spectrum_csv} missing columns: {sorted(required - set(sdf.columns))}")

    sdf = sdf.copy()
    sdf["U_imp"] = pd.to_numeric(sdf["U_imp"], errors="coerce")
    sdf["Frequency"] = pd.to_numeric(sdf["Frequency"], errors="coerce")
    sdf["Amplitude"] = pd.to_numeric(sdf["Amplitude"], errors="coerce")
    sdf = sdf.dropna(subset=["U_imp", "Frequency", "Amplitude"])

    # Choose closest U_imp
    u_values = np.sort(sdf["U_imp"].unique())
    if len(u_values) == 0:
        raise SystemExit(f"No valid U_imp values in {spectrum_csv}")

    u_imp_used = float(u_values[np.argmin(np.abs(u_values - float(u_imp_target)))])
    abs_delta = abs(u_imp_used - float(u_imp_target))
    if abs_delta > float(max_abs_delta_allowed):
        raise SystemExit(
            f"U_imp target {u_imp_target} too far from nearest available {u_imp_used} (abs_delta={abs_delta}, allowed={max_abs_delta_allowed})."
        )

    block = sdf[sdf["U_imp"] == u_imp_used].copy()
    block = block.sort_values("Frequency")
    f = block["Frequency"].to_numpy(dtype=float)
    a = block["Amplitude"].to_numpy(dtype=float)

    # Clamp band
    fmin_used = float(max(float(fmin), float(np.min(f))))
    fmax_used = float(min(float(fmax), float(np.max(f))))
    mask = (f >= fmin_used) & (f <= fmax_used)
    f_sel = f[mask]
    a_sel = a[mask]
    if len(f_sel) < 2:
        raise SystemExit(f"Not enough spectral points in band [{fmin_used},{fmax_used}] for {spectrum_csv} at U_imp={u_imp_used}")

    # NumPy compatibility: use trapezoid (trapz removed in newer versions)
    o_val = float(np.trapezoid(a_sel, f_sel))
    return o_val, u_imp_used, fmin_used, fmax_used


def _first_crossing_time(df: pd.DataFrame, time_col: str, cq_col: str, c_min: float) -> Optional[float]:
    below = df[cq_col].to_numpy(dtype=float) < float(c_min)
    if not np.any(below):
        return None
    idx = int(np.argmax(below))
    return float(df.iloc[idx][time_col])


def _plot_cq_only(df: pd.DataFrame, run_id: str, time_col: str, cq_col: str, out_png: Path, c_min: float) -> None:
    t = df[time_col].to_numpy(dtype=float)
    cq = df[cq_col].to_numpy(dtype=float)

    plt.figure()
    plt.plot(t, cq, label="Cq_raw")
    plt.axhline(float(c_min), linestyle="--", linewidth=1.0, label="C_min")
    plt.xlabel("t")
    plt.ylabel("Cq")
    plt.title(f"{run_id}: Cq only")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def _plot_qcc_full(df: pd.DataFrame, run_id: str, time_col: str, out_png: Path, c_min: float) -> None:
    t = df[time_col].to_numpy(dtype=float)

    plt.figure()
    for col in ["Cq", "Sigma"]:
        if col in df.columns:
            plt.plot(t, df[col].to_numpy(dtype=float), label=col)
    plt.axhline(float(c_min), linestyle="--", linewidth=1.0, label="C_min (on Cq scale)")
    plt.xlabel("t")
    plt.ylabel("value")
    plt.title(f"{run_id}: Cq and Sigma")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def _parse_runs_index(index_csv: Path) -> list[RunRow]:
    df = pd.read_csv(index_csv)
    required = {"run_id", "cq_csv", "time_col", "cq_col", "r_definition", "r_value", "mode"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"runs index missing columns: {missing}")

    rows: list[RunRow] = []
    for _, r in df.iterrows():
        rows.append(
            RunRow(
                run_id=str(r["run_id"]),
                cq_csv=str(r["cq_csv"]),
                time_col=str(r["time_col"]),
                cq_col=str(r["cq_col"]),
                spectrum_csv=str(r.get("spectrum_csv", "") or ""),
                u_imp=_safe_float(r.get("u_imp", None)),
                o_method=str(r.get("o_method", "") or ""),
                o_fmin=_safe_float(r.get("o_fmin", None)),
                o_fmax=_safe_float(r.get("o_fmax", None)),
                r_definition=str(r.get("r_definition", "R_constant") or "R_constant"),
                r_value=float(r.get("r_value", 0.0)),
                mode=str(r.get("mode", "qcc_full") or "qcc_full"),
                notes=str(r.get("notes", "") or ""),
            )
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-index", required=True, help="CSV index of runs")
    ap.add_argument("--mapping", required=True, help="mapping.json path")
    ap.add_argument("--c-min", required=True, type=float, help="C_min threshold on Cq")
    ap.add_argument("--out-root", required=True, help="Output root directory")
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    run_dir = out_root / "runs" / _now_tag()
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)
    contracts_dir.mkdir(parents=True, exist_ok=True)

    mapping_path = Path(args.mapping).resolve()
    mapping = _read_mapping(mapping_path)

    index_path = Path(args.runs_index).resolve()
    rows = _parse_runs_index(index_path)

    # Copy contracts into run (audit)
    (contracts_dir / "mapping.json").write_text(mapping_path.read_text(encoding="utf-8"), encoding="utf-8")
    (contracts_dir / "qcc_runs_index.csv").write_text(index_path.read_text(encoding="utf-8"), encoding="utf-8")

    guards = mapping.get("guards", {})
    u_imp_target_default = float(guards.get("u_imp_target_default", 2.5))
    max_abs_delta_allowed = float(guards.get("u_imp_max_abs_delta_allowed", 0.25))
    require_time_strict = bool(guards.get("require_strictly_increasing_time", True))

    per_run_summary: Dict[str, Any] = {}
    events_rows = []

    for row in rows:
        cq_path = Path(row.cq_csv).resolve()
        if not cq_path.exists():
            raise SystemExit(f"Missing cq_csv for run {row.run_id}: {cq_path}")

        df = pd.read_csv(cq_path)
        if row.time_col not in df.columns or row.cq_col not in df.columns:
            raise SystemExit(
                f"Run {row.run_id}: missing columns time_col={row.time_col} or cq_col={row.cq_col} in {cq_path}"
            )

        df = df.copy()
        df["t"] = pd.to_numeric(df[row.time_col], errors="coerce")
        df["Cq"] = pd.to_numeric(df[row.cq_col], errors="coerce")
        df = df.dropna(subset=["t", "Cq"]).reset_index(drop=True)

        if require_time_strict:
            _require_time_strict(df, "t")

        mode = row.mode.strip().lower()
        if mode not in ("qcc_full", "cq_only"):
            raise SystemExit(f"Run {row.run_id}: unknown mode {row.mode}. Allowed: qcc_full, cq_only.")

        o_val = None
        u_imp_used = None
        fmin_used = None
        fmax_used = None

        if mode == "qcc_full":
            spec_path = Path(row.spectrum_csv).resolve()
            if not spec_path.exists():
                raise SystemExit(f"Run {row.run_id}: qcc_full requires spectrum_csv, missing: {spec_path}")

            u_target = float(row.u_imp) if row.u_imp is not None else u_imp_target_default
            fmin = float(row.o_fmin) if row.o_fmin is not None else 0.0
            fmax = float(row.o_fmax) if row.o_fmax is not None else float("inf")
            if not math.isfinite(fmax):
                fmax = 1e9

            o_val, u_imp_used, fmin_used, fmax_used = _bandpower_from_spectrum(
                spectrum_csv=spec_path,
                u_imp_target=u_target,
                fmin=fmin,
                fmax=fmax,
                max_abs_delta_allowed=max_abs_delta_allowed,
            )

            # R
            r_val = float(row.r_value)
            df["O"] = float(o_val)
            df["R"] = float(r_val)
            df["Sigma"] = _compute_sigma_constant_o(df, "t", float(o_val), float(r_val))

            out_ts = tables_dir / f"timeseries_{row.run_id}.csv"
            df[["t", "Cq", "O", "R", "Sigma"]].to_csv(out_ts, index=False)

            _plot_qcc_full(df, row.run_id, "t", figs_dir / f"plot_{row.run_id}.png", float(args.c_min))

        else:
            # Cq only
            out_ts = tables_dir / f"timeseries_{row.run_id}.csv"
            df[["t", "Cq"]].to_csv(out_ts, index=False)
            _plot_cq_only(df, row.run_id, "t", "Cq", figs_dir / f"plot_{row.run_id}.png", float(args.c_min))

        # Events
        t_star = _first_crossing_time(df, "t", "Cq", float(args.c_min))
        sigma_at_t_star = None
        if (mode == "qcc_full") and (t_star is not None):
            idx = int(np.argmax(df["Cq"].to_numpy(dtype=float) < float(args.c_min)))
            sigma_at_t_star = float(df.iloc[idx]["Sigma"])

        per_run_summary[row.run_id] = {
            "mode": mode,
            "cq_csv": str(cq_path),
            "time_col": row.time_col,
            "cq_col": row.cq_col,
            "c_min": float(args.c_min),
            "n": int(len(df)),
            "t_min": float(df["t"].min()) if len(df) else float("nan"),
            "t_max": float(df["t"].max()) if len(df) else float("nan"),
            "Cq_min": float(df["Cq"].min()) if len(df) else float("nan"),
            "Cq_max": float(df["Cq"].max()) if len(df) else float("nan"),
            "has_t_star": t_star is not None,
            "t_star": t_star,
            "sigma_at_t_star": sigma_at_t_star,
            "O": o_val,
            "R": float(row.r_value),
            "u_imp_target": float(row.u_imp) if row.u_imp is not None else None,
            "u_imp_used": u_imp_used,
            "o_band_fmin_used": fmin_used,
            "o_band_fmax_used": fmax_used,
            "notes": row.notes,
        }

        events_rows.append(
            {
                "run_id": row.run_id,
                "mode": mode,
                "t_star": t_star,
                "sigma_at_t_star": sigma_at_t_star,
            }
        )

    # Write events and summary
    events_df = pd.DataFrame(events_rows)
    events_df.to_csv(tables_dir / "events.csv", index=False)

    summary = {
        "mapping_version": mapping.get("version"),
        "created_at": _now_tag(),
        "runs_index": str(index_path),
        "mapping_path": str(mapping_path),
        "runs": per_run_summary,
        "notes": "No global verdict. Cq-only runs do not compute Sigma until an independent O is provided.",
    }
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Compare plot for Cq across runs
    plt.figure()
    for run_id, info in per_run_summary.items():
        ts_path = tables_dir / f"timeseries_{run_id}.csv"
        tdf = pd.read_csv(ts_path)
        if "t" in tdf.columns and "Cq" in tdf.columns:
            plt.plot(tdf["t"].to_numpy(dtype=float), tdf["Cq"].to_numpy(dtype=float), label=run_id)
    plt.axhline(float(args.c_min), linestyle="--", linewidth=1.0, label="C_min")
    plt.xlabel("t")
    plt.ylabel("Cq")
    plt.title("Compare Cq across runs")
    plt.legend()
    plt.tight_layout()
    plt.savefig(figs_dir / "compare_Cq.png", dpi=150)
    plt.close()

    # Manifest sha256 over run_dir (includes contracts, tables, figures)
    write_manifest_sha256(run_dir, run_dir / "manifest.json")

    # Pointer
    (out_root / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")

    print(f"OK: run_dir={run_dir}")


if __name__ == "__main__":
    main()
