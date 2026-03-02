# tools/qcc_real_data_from_runs_index.py
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from make_manifest import write_manifest_sha256


@dataclass
class RunSpec:
    run_id: str
    cq_csv: str
    time_col: str
    cq_col: str
    spectrum_csv: Optional[str]
    u_imp_target: Optional[float]
    r_value: float


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _read_runs_index(path: Path) -> List[RunSpec]:
    df = pd.read_csv(path)
    required = ["run_id", "cq_csv", "time_col", "cq_col", "r_value"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"runs_index missing columns: {missing}")

    specs: List[RunSpec] = []
    for _, row in df.iterrows():
        spec = RunSpec(
            run_id=str(row["run_id"]),
            cq_csv=str(row["cq_csv"]),
            time_col=str(row["time_col"]),
            cq_col=str(row["cq_col"]),
            spectrum_csv=str(row["spectrum_csv"]) if "spectrum_csv" in df.columns and not pd.isna(row.get("spectrum_csv")) else None,
            u_imp_target=float(row["u_imp_target"]) if "u_imp_target" in df.columns and not pd.isna(row.get("u_imp_target")) else None,
            r_value=float(row["r_value"]),
        )
        specs.append(spec)
    return specs


def _compute_sigma(t: np.ndarray, o: np.ndarray, r: np.ndarray) -> np.ndarray:
    if len(t) < 2:
        return np.zeros(len(t), dtype=float)
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise SystemExit("Time column must be strictly increasing for Sigma integration.")
    resid = np.maximum(0.0, o - r)
    sigma = np.zeros_like(t, dtype=float)
    for k in range(1, len(t)):
        sigma[k] = sigma[k - 1] + resid[k - 1] * dt[k - 1]
    return sigma


def _first_crossing(t: np.ndarray, cq: np.ndarray, c_min: float) -> Tuple[Optional[float], Optional[int]]:
    below = cq < float(c_min)
    if not np.any(below):
        return None, None
    idx = int(np.argmax(below))
    return float(t[idx]), idx


def _compute_O_from_spectrum(spectrum_csv: Path, u_imp_target: float) -> Dict[str, Any]:
    spec = pd.read_csv(spectrum_csv)
    required = {"U_imp", "Frequency", "Amplitude"}
    if not required.issubset(set(spec.columns)):
        raise SystemExit(f"Spectrum {spectrum_csv} must have columns {sorted(required)}")

    u_vals = spec["U_imp"].to_numpy(dtype=float)
    uniq = np.unique(u_vals)
    u_imp_used = float(uniq[np.argmin(np.abs(uniq - float(u_imp_target)))])
    sub = spec[spec["U_imp"].astype(float) == u_imp_used].copy()
    sub = sub.sort_values("Frequency")
    f = sub["Frequency"].to_numpy(dtype=float)
    a = sub["Amplitude"].to_numpy(dtype=float)

    # "Bandpower" simple: intégrale trapézoïdale sur toute la bande disponible
    # NumPy 2.x peut ne plus exposer np.trapz; utiliser np.trapezoid si disponible
    if hasattr(np, "trapezoid"):
        O = float(np.trapezoid(a, f))
    else:
        O = float(np.trapz(a, f))
    return {"O": O, "u_imp_used": u_imp_used, "u_imp_target": float(u_imp_target), "f_min": float(np.min(f)), "f_max": float(np.max(f))}


def _plot_run(df: pd.DataFrame, run_id: str, c_min: float, out_png: Path) -> None:
    t = df["t"].to_numpy(dtype=float)
    plt.figure()
    plt.plot(t, df["Cq"].to_numpy(dtype=float), label="Cq")
    plt.plot(t, df["Sigma"].to_numpy(dtype=float), label="Sigma")
    plt.axhline(float(c_min), linestyle="--", linewidth=1.0, label="C_min")
    plt.xlabel("t")
    plt.ylabel("valeur")
    plt.title(f"QCC run {run_id}")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def _plot_compare_cq(runs: Dict[str, pd.DataFrame], out_png: Path) -> None:
    plt.figure()
    for run_id, df in runs.items():
        t = df["t"].to_numpy(dtype=float)
        plt.plot(t, df["Cq"].to_numpy(dtype=float), label=run_id)
    plt.xlabel("t")
    plt.ylabel("Cq")
    plt.title("Comparaison Cq(t) par run")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def run_pipeline(runs_index: Path, out_root: Path, c_min: float) -> Path:
    out_root = out_root.resolve()
    run_dir = out_root / "runs" / _now_tag()
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    specs = _read_runs_index(runs_index)

    all_summaries: List[Dict[str, Any]] = []
    run_frames: Dict[str, pd.DataFrame] = {}

    for spec in specs:
        cq_path = (runs_index.parent / spec.cq_csv).resolve() if not Path(spec.cq_csv).is_absolute() else Path(spec.cq_csv)
        df = pd.read_csv(cq_path)

        if spec.time_col not in df.columns or spec.cq_col not in df.columns:
            raise SystemExit(f"{spec.run_id}: missing columns in {cq_path}: need {spec.time_col}, {spec.cq_col}")

        t = pd.to_numeric(df[spec.time_col], errors="coerce").to_numpy(dtype=float)
        cq = pd.to_numeric(df[spec.cq_col], errors="coerce").to_numpy(dtype=float)

        mask = np.isfinite(t) & np.isfinite(cq)
        t = t[mask]
        cq = cq[mask]

        # Normalisation prudente: si amplitude dépasse 1 en absolu, on normalise par max abs
        cq_max_abs = float(np.max(np.abs(cq))) if len(cq) else 1.0
        cq_norm = cq / cq_max_abs if cq_max_abs > 1.0 else cq

        # O et R
        O_info: Dict[str, Any] = {"O": None, "method": None}
        if spec.spectrum_csv and spec.u_imp_target is not None:
            spec_path = (runs_index.parent / spec.spectrum_csv).resolve() if not Path(spec.spectrum_csv).is_absolute() else Path(spec.spectrum_csv)
            oi = _compute_O_from_spectrum(spec_path, float(spec.u_imp_target))
            O_info = {"method": "trapz_fullband_at_u_imp", **oi, "spectrum_csv": str(spec.spectrum_csv)}
            O_val = float(oi["O"])
        else:
            # fallback strict: O constant = 0 (no exposure provided)
            O_val = 0.0
            O_info = {"method": "constant_zero", "O": O_val}

        R_val = float(spec.r_value)

        O = np.full_like(t, O_val, dtype=float)
        R = np.full_like(t, R_val, dtype=float)
        sigma = _compute_sigma(t, O, R)

        df_out = pd.DataFrame({"t": t, "Cq": cq_norm, "O": O, "R": R, "Sigma": sigma})
        run_frames[spec.run_id] = df_out

        t_star, idx_star = _first_crossing(t, cq_norm, c_min)
        sigma_at_t_star = float(sigma[idx_star]) if idx_star is not None else None

        # save per-run timeseries
        ts_path = tables_dir / f"timeseries_{spec.run_id}.csv"
        df_out.to_csv(ts_path, index=False)

        events = {
            "run_id": spec.run_id,
            "c_min": float(c_min),
            "t_star": t_star,
            "sigma_at_t_star": sigma_at_t_star,
        }
        (tables_dir / f"events_{spec.run_id}.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

        # plot
        _plot_run(df_out, spec.run_id, c_min, figs_dir / f"plot_{spec.run_id}.png")

        all_summaries.append(
            {
                "run_id": spec.run_id,
                "cq_csv": spec.cq_csv,
                "time_col": spec.time_col,
                "cq_col": spec.cq_col,
                "c_min": float(c_min),
                "O": float(O_val),
                "R": float(R_val),
                "O_info": O_info,
                "t_star": t_star,
                "sigma_at_t_star": sigma_at_t_star,
                "n": int(len(df_out)),
            }
        )

    # aggregate summary
    agg = {
        "runs_index": str(runs_index.as_posix()),
        "created_at": _now_tag(),
        "notes": "Aucun verdict global. Mesures et événements par run seulement.",
        "runs": all_summaries,
    }
    (tables_dir / "summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    # compare plot
    if run_frames:
        _plot_compare_cq(run_frames, figs_dir / "compare_Cq.png")

    # manifest
    write_manifest_sha256(run_dir, run_dir / "manifest.json")

    # LATEST_RUN
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")

    return run_dir


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-index", required=True, help="CSV index des runs")
    ap.add_argument("--out-root", required=True, help="Répertoire de sortie")
    ap.add_argument("--c-min", type=float, default=0.35, help="Seuil C_min")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    runs_index = Path(args.runs_index)
    out_root = Path(args.out_root)
    run_dir = run_pipeline(runs_index, out_root, float(args.c_min))
    print(f"OK: run_dir={run_dir}")


if __name__ == "__main__":
    main()
