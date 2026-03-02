from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

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
    spectrum_csv: str
    u_imp_target: float
    o_method: str
    r_definition: str
    r_value: float


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_u_imp_block(df: pd.DataFrame, u_imp_target: float) -> Tuple[float, pd.DataFrame]:
    # df columns: U_imp, Frequency, Amplitude
    u_vals = np.sort(df["U_imp"].unique().astype(float))
    if len(u_vals) == 0:
        raise SystemExit("Aucune valeur U_imp dans le spectre.")
    idx = int(np.argmin(np.abs(u_vals - float(u_imp_target))))
    u_used = float(u_vals[idx])
    block = df[df["U_imp"].astype(float) == u_used].copy()
    return u_used, block


def _band_integral(block: pd.DataFrame, f_min: float, f_max: float) -> float:
    blk = block.copy()
    blk["Frequency"] = pd.to_numeric(blk["Frequency"], errors="coerce")
    blk["Amplitude"] = pd.to_numeric(blk["Amplitude"], errors="coerce")
    blk = blk.dropna(subset=["Frequency", "Amplitude"]).sort_values("Frequency")
    blk = blk[(blk["Frequency"] >= float(f_min)) & (blk["Frequency"] <= float(f_max))]
    if len(blk) < 2:
        return float("nan")
    f = blk["Frequency"].to_numpy(dtype=float)
    a = blk["Amplitude"].to_numpy(dtype=float)
    # np.trapezoid est la forme actuelle recommandée; fallback si besoin.
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(a, f))
    return float(np.trapz(a, f))


def _compute_sigma(time_vals: np.ndarray, o_val: float, r_val: float) -> np.ndarray:
    t = time_vals.astype(float)
    if len(t) < 2:
        return np.zeros_like(t, dtype=float)
    dt = np.diff(t)
    dt = np.where(dt > 0, dt, 0.0)
    resid = max(0.0, float(o_val) - float(r_val))
    sigma = np.zeros_like(t, dtype=float)
    for k in range(1, len(t)):
        sigma[k] = sigma[k - 1] + resid * dt[k - 1]
    return sigma


def _first_crossing_time(t: np.ndarray, cq: np.ndarray, c_min: float) -> Tuple[float | None, float | None]:
    below = cq < float(c_min)
    if not np.any(below):
        return None, None
    idx = int(np.argmax(below))
    return float(t[idx]), idx


def _plot_run(df: pd.DataFrame, run_id: str, out_png: Path, c_min: float) -> None:
    t = df["t"].to_numpy(dtype=float)

    plt.figure()
    plt.plot(t, df["Cq"].to_numpy(dtype=float), label="Cq")
    plt.axhline(float(c_min), linestyle="--", linewidth=1.0, label="C_min")
    plt.plot(t, df["Sigma"].to_numpy(dtype=float), label="Sigma")
    plt.xlabel("t")
    plt.ylabel("valeur")
    plt.title(f"{run_id}: Cq et Sigma")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def _plot_compare_cq(runs: Dict[str, pd.DataFrame], out_png: Path) -> None:
    plt.figure()
    for run_id, df in runs.items():
        plt.plot(df["t"].to_numpy(dtype=float), df["Cq"].to_numpy(dtype=float), label=run_id)
    plt.xlabel("t")
    plt.ylabel("Cq")
    plt.title("Comparaison Cq(t)")
    plt.legend()
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()


def _copy_contracts(run_dir: Path, mapping_path: Path, runs_index_path: Path, data_contract_path: Path) -> None:
    cdir = run_dir / "contracts"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "mapping.json").write_text(mapping_path.read_text(encoding="utf-8"), encoding="utf-8")
    (cdir / "qcc_runs_index.csv").write_text(runs_index_path.read_text(encoding="utf-8"), encoding="utf-8")
    if data_contract_path.exists():
        (cdir / "DATA_CONTRACT.md").write_text(data_contract_path.read_text(encoding="utf-8"), encoding="utf-8")


def run(runs_index: Path, mapping: Path, data_root: Path, out_root: Path) -> Path:
    out_root = out_root.resolve()
    run_dir = out_root / "runs" / _now_tag()
    tables = run_dir / "tables"
    figs = run_dir / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    m = _load_json(mapping)
    c_min = float(m.get("c_min", 0.35))

    o_cfg = m.get("o", {})
    u_imp_target_default = float(o_cfg.get("u_imp_target", 2.5))
    fband = o_cfg.get("frequency_band", {})
    f_min = float(fband.get("f_min", 0.0))
    f_max = float(fband.get("f_max", 1e9))
    u_imp_max_abs_delta_allowed = float(o_cfg.get("u_imp_max_abs_delta_allowed", 1e9))

    r_cfg = m.get("r", {})
    r_value_default = float(r_cfg.get("value", 0.0))

    idx_df = pd.read_csv(runs_index)
    required_cols = ["run_id", "cq_csv", "time_col", "cq_col", "spectrum_csv", "u_imp_target", "o_method", "r_definition", "r_value"]
    missing = [c for c in required_cols if c not in idx_df.columns]
    if missing:
        raise SystemExit(f"Colonnes manquantes dans runs_index: {missing}")

    runs_out: Dict[str, pd.DataFrame] = {}
    events: Dict[str, Dict] = {}
    summary_runs: Dict[str, Dict] = {}

    for _, row in idx_df.iterrows():
        spec = RunSpec(
            run_id=str(row["run_id"]),
            cq_csv=str(row["cq_csv"]),
            time_col=str(row["time_col"]),
            cq_col=str(row["cq_col"]),
            spectrum_csv=str(row["spectrum_csv"]),
            u_imp_target=float(row["u_imp_target"]) if str(row["u_imp_target"]).strip() else u_imp_target_default,
            o_method=str(row["o_method"]),
            r_definition=str(row["r_definition"]),
            r_value=float(row["r_value"]) if str(row["r_value"]).strip() else r_value_default,
        )

        cq_path = (data_root / spec.cq_csv).resolve()
        sp_path = (data_root / spec.spectrum_csv).resolve()

        if not cq_path.exists():
            raise SystemExit(f"Fichier cq_csv introuvable: {cq_path}")
        if not sp_path.exists():
            raise SystemExit(f"Fichier spectrum_csv introuvable: {sp_path}")

        cq_df = pd.read_csv(cq_path)
        if spec.time_col not in cq_df.columns or spec.cq_col not in cq_df.columns:
            raise SystemExit(f"Colonnes manquantes dans {cq_path.name}: {spec.time_col}, {spec.cq_col}")

        t = pd.to_numeric(cq_df[spec.time_col], errors="coerce").to_numpy(dtype=float)
        cq = pd.to_numeric(cq_df[spec.cq_col], errors="coerce").to_numpy(dtype=float)
        keep = np.isfinite(t) & np.isfinite(cq)
        t = t[keep]
        cq = cq[keep]

        order = np.argsort(t)
        t = t[order]
        cq = cq[order]

        sp_df = pd.read_csv(sp_path)
        for col in ["U_imp", "Frequency", "Amplitude"]:
            if col not in sp_df.columns:
                raise SystemExit(f"Colonne manquante dans {sp_path.name}: {col}")

        u_used, block = _select_u_imp_block(sp_df, spec.u_imp_target)
        u_delta = abs(u_used - float(spec.u_imp_target))
        if u_delta > u_imp_max_abs_delta_allowed:
            raise SystemExit(f"U_imp trop éloigné du target: target={spec.u_imp_target}, used={u_used}, delta={u_delta}, allowed={u_imp_max_abs_delta_allowed}")

        o_val = _band_integral(block, f_min=f_min, f_max=f_max)
        if not np.isfinite(o_val):
            raise SystemExit(f"Calcul O invalide pour {spec.run_id}. Vérifier bande fréquence et données spectre.")

        r_val = float(spec.r_value) if spec.r_definition.strip().lower() == "constant" else float(spec.r_value)

        sigma = _compute_sigma(t, o_val=o_val, r_val=r_val)

        out_df = pd.DataFrame({"t": t, "Cq": cq, "O": float(o_val), "R": float(r_val), "Sigma": sigma})
        out_csv = tables / f"timeseries_{spec.run_id}.csv"
        out_df.to_csv(out_csv, index=False)

        t_star, idx_star = _first_crossing_time(t, cq, c_min=c_min)
        sigma_at_t_star = None
        if idx_star is not None:
            sigma_at_t_star = float(sigma[int(idx_star)])

        events[spec.run_id] = {
            "run_id": spec.run_id,
            "c_min": c_min,
            "t_star": t_star,
            "sigma_at_t_star": sigma_at_t_star,
        }
        (tables / f"events_{spec.run_id}.json").write_text(json.dumps(events[spec.run_id], indent=2), encoding="utf-8")

        _plot_run(out_df, spec.run_id, figs / f"plot_{spec.run_id}.png", c_min=c_min)

        runs_out[spec.run_id] = out_df
        summary_runs[spec.run_id] = {
            "run_id": spec.run_id,
            "cq_source": {"file": spec.cq_csv, "time_col": spec.time_col, "cq_col": spec.cq_col},
            "spectrum_source": {"file": spec.spectrum_csv},
            "u_imp_target": float(spec.u_imp_target),
            "u_imp_used": float(u_used),
            "u_imp_abs_delta": float(u_delta),
            "o_method": spec.o_method,
            "o_value": float(o_val),
            "frequency_band": {"f_min": f_min, "f_max": f_max},
            "r_definition": spec.r_definition,
            "r_value": float(r_val),
            "n_points": int(len(out_df)),
            "t_min": float(np.min(t)) if len(t) else float("nan"),
            "t_max": float(np.max(t)) if len(t) else float("nan"),
            "sigma_final": float(sigma[-1]) if len(sigma) else float("nan"),
            "has_t_star": t_star is not None,
            "t_star": t_star,
            "sigma_at_t_star": sigma_at_t_star,
        }

    _plot_compare_cq(runs_out, figs / "compare_Cq.png")

    data_contract_path = (data_root / "DATA_CONTRACT.md").resolve()
    _copy_contracts(run_dir, mapping, runs_index, data_contract_path)

    summary = {
        "dataset": m.get("dataset", "unknown"),
        "version": m.get("version", "unknown"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "c_min": c_min,
        "notes": "Aucun verdict global. Mesures, événements et traçabilité seulement.",
        "runs": summary_runs,
    }
    (tables / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_manifest_sha256(run_dir, run_dir / "manifest.json")

    (out_root / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")

    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-index", required=True)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    run_dir = run(
        runs_index=Path(args.runs_index),
        mapping=Path(args.mapping),
        data_root=Path(args.data_root),
        out_root=Path(args.out_root),
    )
    print(f"OK: run_dir={run_dir}")


if __name__ == "__main__":
    main()
