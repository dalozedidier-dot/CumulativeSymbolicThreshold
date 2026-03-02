# tools/qcc_real_data_from_runs_index.py
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from make_manifest import write_manifest_sha256


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _pick_u_imp_nearest(spec: pd.DataFrame, target: float) -> Tuple[float, pd.DataFrame]:
    # spec: columns U_imp, Frequency, Amplitude
    u_vals = np.unique(spec["U_imp"].to_numpy(dtype=float))
    if len(u_vals) == 0:
        raise ValueError("Spectrum has no U_imp values")
    idx = int(np.argmin(np.abs(u_vals - target)))
    u_used = float(u_vals[idx])
    sub = spec[spec["U_imp"].astype(float) == u_used].copy()
    sub = sub.sort_values("Frequency")
    return u_used, sub


def _integrate_bandpower(sub: pd.DataFrame, f_min: float, f_max: float) -> float:
    f = sub["Frequency"].to_numpy(dtype=float)
    a = sub["Amplitude"].to_numpy(dtype=float)
    mask = (f >= float(f_min)) & (f <= float(f_max))
    f2 = f[mask]
    a2 = a[mask]
    if len(f2) < 2:
        return float("nan")
    # NumPy 2.0+: trapezoid; garder un fallback.
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(a2, f2))
    return float(np.trapz(a2, f2))


def _compute_sigma(t: np.ndarray, o_val: float, r_val: float) -> np.ndarray:
    if len(t) == 0:
        return np.array([], dtype=float)
    dt = np.diff(t)
    dt = np.where(dt > 0, dt, 0.0)
    resid = max(0.0, float(o_val) - float(r_val))
    sigma = np.zeros_like(t, dtype=float)
    for k in range(1, len(t)):
        sigma[k] = sigma[k - 1] + resid * dt[k - 1]
    return sigma


def _first_crossing(t: np.ndarray, cq: np.ndarray, c_min: float) -> Optional[Tuple[float, int]]:
    below = cq < float(c_min)
    if not np.any(below):
        return None
    idx = int(np.argmax(below))
    return float(t[idx]), idx


def _plot_run(df: pd.DataFrame, run_id: str, out_png: Path, c_min: float) -> None:
    t = df["t"].to_numpy(dtype=float)
    plt.figure()
    plt.plot(t, df["Cq"].to_numpy(dtype=float), label="Cq")
    if "Sigma" in df.columns:
        plt.plot(t, df["Sigma"].to_numpy(dtype=float), label="Sigma")
    plt.axhline(float(c_min), linestyle="--", linewidth=1.0, label="C_min")
    plt.xlabel("t")
    plt.ylabel("valeur")
    plt.title(run_id)
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def _plot_compare_cq(runs: Dict[str, pd.DataFrame], out_png: Path) -> None:
    plt.figure()
    for run_id, df in runs.items():
        t = df["t"].to_numpy(dtype=float)
        cq = df["Cq"].to_numpy(dtype=float)
        plt.plot(t, cq, label=run_id)
    plt.xlabel("t")
    plt.ylabel("Cq")
    plt.title("Compare Cq across runs")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


@dataclass
class RunSpec:
    run_id: str
    mode: str
    cq_csv: str
    time_col: str
    cq_col: str
    spectrum_csv: str
    u_imp: Optional[float]
    o_method: str
    r_definition: str
    r_value: Optional[float]


def _load_runs_index(path: Path) -> list[RunSpec]:
    df = pd.read_csv(path)
    specs: list[RunSpec] = []
    for _, row in df.iterrows():
        specs.append(
            RunSpec(
                run_id=str(row["run_id"]),
                mode=str(row.get("mode", "qcc")).strip(),
                cq_csv=str(row["cq_csv"]),
                time_col=str(row["time_col"]),
                cq_col=str(row["cq_col"]),
                spectrum_csv=str(row.get("spectrum_csv", "") or ""),
                u_imp=_to_float(row["u_imp"]) if "u_imp" in row and str(row["u_imp"]) != "" else None,
                o_method=str(row.get("o_method", "bandpower")),
                r_definition=str(row.get("r_definition", "R_constant")),
                r_value=_to_float(row["r_value"]) if "r_value" in row and str(row["r_value"]) != "" else None,
            )
        )
    return specs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-index", required=True)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--data-root", default="", help="Racine des données (optionnel)")
    ap.add_argument("--c-min", required=False, type=float, default=None)
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    runs_index = Path(args.runs_index)
    mapping_path = Path(args.mapping)
    data_root = Path(args.data_root) if args.data_root else mapping_path.parent

    mapping = _read_json(mapping_path)
    # c_min: priorité CLI, sinon mapping, sinon 0.35
    c_min = args.c_min
    if c_min is None:
        c_min = float(mapping.get("c_min", mapping.get("c_min_default", 0.35)))

    u_imp_target = float(mapping.get("u_imp_target", 2.5))
    u_imp_max_abs_delta_allowed = float(mapping.get("u_imp_max_abs_delta_allowed", 0.25))
    band = mapping.get("o_band", {"f_min": 0.0, "f_max": 1e9})
    f_min = float(band.get("f_min", 0.0))
    f_max = float(band.get("f_max", 1e9))

    out_root = Path(args.out_root).resolve()
    run_dir = out_root / "runs" / _now_tag()
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    for d in (tables_dir, figs_dir, contracts_dir):
        d.mkdir(parents=True, exist_ok=True)

    # copier contrats pour audit
    (contracts_dir / "mapping.json").write_text(mapping_path.read_text(encoding="utf-8"), encoding="utf-8")
    (contracts_dir / "qcc_runs_index.csv").write_text(runs_index.read_text(encoding="utf-8"), encoding="utf-8")
    dc = mapping.get("data_contract_path")
    if dc:
        dc_path = (mapping_path.parent / str(dc)).resolve()
        if dc_path.exists():
            (contracts_dir / "DATA_CONTRACT.md").write_text(dc_path.read_text(encoding="utf-8"), encoding="utf-8")

    specs = _load_runs_index(runs_index)

    summary: Dict[str, Any] = {
        "c_min": float(c_min),
        "u_imp_target": u_imp_target,
        "u_imp_max_abs_delta_allowed": u_imp_max_abs_delta_allowed,
        "o_band": {"f_min": f_min, "f_max": f_max},
        "runs": {},
        "notes": "No global verdict. Measurements and events only.",
    }

    cq_runs_for_compare: Dict[str, pd.DataFrame] = {}

    for spec in specs:
        cq_path = (data_root / "raw" / spec.cq_csv).resolve() if not Path(spec.cq_csv).exists() else Path(spec.cq_csv)
        df_cq = pd.read_csv(cq_path)
        if spec.time_col not in df_cq.columns or spec.cq_col not in df_cq.columns:
            raise SystemExit(f"[{spec.run_id}] Missing columns in {cq_path.name}")

        t = pd.to_numeric(df_cq[spec.time_col], errors="coerce").to_numpy(dtype=float)
        cq_raw = pd.to_numeric(df_cq[spec.cq_col], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(t) & np.isfinite(cq_raw)
        t = t[mask]
        cq_raw = cq_raw[mask]

        # enforce strict increasing time (drop non-increasing)
        order = np.argsort(t)
        t = t[order]
        cq_raw = cq_raw[order]
        keep = np.ones_like(t, dtype=bool)
        keep[1:] = np.diff(t) > 0
        t = t[keep]
        cq_raw = cq_raw[keep]

        run_df = pd.DataFrame({"t": t, "Cq": cq_raw})

        run_info: Dict[str, Any] = {
            "mode": spec.mode,
            "cq_source": str(spec.cq_csv),
            "time_col": spec.time_col,
            "cq_col": spec.cq_col,
            "n": int(len(run_df)),
        }

        if spec.mode.strip().lower() == "cq_only":
            # No Sigma, no O/R computation.
            ts_path = tables_dir / f"timeseries_{spec.run_id}.csv"
            run_df.to_csv(ts_path, index=False)
            _plot_run(run_df, spec.run_id, figs_dir / f"plot_{spec.run_id}.png", float(c_min))

            summary["runs"][spec.run_id] = {**run_info, "has_sigma": False}
            cq_runs_for_compare[spec.run_id] = run_df
            continue

        # QCC mode: compute O from spectrum if available, else fail (strict)
        if not spec.spectrum_csv:
            raise SystemExit(f"[{spec.run_id}] spectrum_csv required for qcc mode")

        spec_path = (data_root / "raw" / spec.spectrum_csv).resolve() if not Path(spec.spectrum_csv).exists() else Path(spec.spectrum_csv)
        df_spec = pd.read_csv(spec_path)
        for col in ("U_imp", "Frequency", "Amplitude"):
            if col not in df_spec.columns:
                raise SystemExit(f"[{spec.run_id}] Missing {col} in spectrum {spec_path.name}")

        u_used, sub = _pick_u_imp_nearest(df_spec, u_imp_target)
        abs_delta = abs(u_used - u_imp_target)
        if abs_delta > u_imp_max_abs_delta_allowed:
            raise SystemExit(f"[{spec.run_id}] |u_imp_used - target| too large: {abs_delta}")

        o_val = _integrate_bandpower(sub, f_min=f_min, f_max=f_max)

        r_val = 0.0
        if spec.r_definition.strip().lower() == "r_constant" and spec.r_value is not None and np.isfinite(spec.r_value):
            r_val = float(spec.r_value)

        sigma = _compute_sigma(t, o_val=o_val, r_val=r_val)
        run_df["Sigma"] = sigma

        # event t*
        crossing = _first_crossing(t, cq_raw, float(c_min))
        if crossing is not None:
            t_star, idx = crossing
            sigma_star = float(sigma[idx])
        else:
            t_star, sigma_star = None, None

        # outputs
        ts_path = tables_dir / f"timeseries_{spec.run_id}.csv"
        run_df.to_csv(ts_path, index=False)
        events_path = tables_dir / f"events_{spec.run_id}.json"
        events_path.write_text(
            json.dumps({"t_star": t_star, "sigma_at_t_star": sigma_star, "c_min": float(c_min)}, indent=2),
            encoding="utf-8",
        )
        _plot_run(run_df, spec.run_id, figs_dir / f"plot_{spec.run_id}.png", float(c_min))

        summary["runs"][spec.run_id] = {
            **run_info,
            "has_sigma": True,
            "o_method": "bandpower_trapezoid",
            "o_val": float(o_val),
            "r_val": float(r_val),
            "spectrum_source": str(spec.spectrum_csv),
            "u_imp_target": u_imp_target,
            "u_imp_used": float(u_used),
            "u_imp_abs_delta": float(abs_delta),
            "f_min": f_min,
            "f_max": f_max,
            "t_star": t_star,
            "sigma_at_t_star": sigma_star,
        }
        cq_runs_for_compare[spec.run_id] = run_df[["t", "Cq"]].copy()

    # compare plot
    if len(cq_runs_for_compare) >= 2:
        _plot_compare_cq(cq_runs_for_compare, figs_dir / "compare_Cq.png")

    # summary
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # manifest
    write_manifest_sha256(run_dir, run_dir / "manifest.json")

    # LATEST_RUN pointer
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")

    print(f"OK: run_dir={run_dir}")


if __name__ == "__main__":
    main()
