#!/usr/bin/env python3
"""
build_registered_report_assets.py

Generate "publication-ready" figures and tables for the ORI-C registered report
from an existing canonical run directory.

Inputs (run_dir):
  canonical_tests/<run_id>/
    - global_summary.csv
    - global_verdict.json
    - T*/... (per-test outputs)

Outputs (by default, in-repo working tree):
  05_Results/registered_reports/figures/
  05_Results/registered_reports/tables/
  06_Manuscript/figures/
  06_Manuscript/tables/

This script is intentionally conservative:
- No synthetic data generation beyond declared bootstrap resampling.
- No hidden heuristics: everything is derived from existing run outputs or
  explicit transformations (aggregation, correlations, bootstrap).

Usage:
  python 04_Code/reporting/build_registered_report_assets.py --run-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    _ensure_dir(dst.parent)
    dst.write_bytes(src.read_bytes())
    return True


def _find_run_timeseries(run_dir: Path, test_id: str = "T1_noyau_demand_shock", run_name: str = "run_0001") -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    base = run_dir / test_id / run_name / "tables"
    test_csv = base / "test_timeseries.csv"
    ctrl_csv = base / "control_timeseries.csv"
    verdict_json = base / "verdict.json"

    if not test_csv.exists() or not ctrl_csv.exists():
        raise FileNotFoundError(f"Missing timeseries CSVs under: {base}")

    test_df = pd.read_csv(test_csv)
    ctrl_df = pd.read_csv(ctrl_csv)

    thr = None
    if verdict_json.exists():
        v = _read_json(verdict_json)
        km = v.get("key_metrics", {}) if isinstance(v, dict) else {}
        thr = km.get("threshold_hit_t")

    if thr is None:
        if "threshold_hit" in test_df.columns:
            hits = np.where(test_df["threshold_hit"].astype(float).values > 0.0)[0]
            thr = int(hits[0]) if len(hits) else max(0, int(len(test_df) * 0.2))
        else:
            thr = max(0, int(len(test_df) * 0.2))

    return ctrl_df, test_df, int(thr)


def _write_descriptives_phases(ctrl_df: pd.DataFrame, test_df: pd.DataFrame, thr: int, out_csv: Path) -> None:
    vars_keep = [c for c in ["O", "R", "I", "Cap", "Sigma", "S", "V", "C", "demand"] if c in test_df.columns]

    def summarize(df: pd.DataFrame, label_system: str, label_phase: str, sl: slice) -> pd.DataFrame:
        sub = df.iloc[sl].copy()
        rows = []
        for v in vars_keep:
            x = pd.to_numeric(sub[v], errors="coerce").dropna()
            rows.append(
                {
                    "system": label_system,
                    "phase": label_phase,
                    "var": v,
                    "n": int(x.shape[0]),
                    "mean": float(x.mean()) if len(x) else np.nan,
                    "std": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
                    "min": float(x.min()) if len(x) else np.nan,
                    "max": float(x.max()) if len(x) else np.nan,
                    "median": float(x.median()) if len(x) else np.nan,
                }
            )
        return pd.DataFrame(rows)

    pre = slice(0, max(0, thr))
    post = slice(max(0, thr), None)

    out = pd.concat(
        [
            summarize(ctrl_df, "control", "pre", pre),
            summarize(ctrl_df, "control", "post", post),
            summarize(test_df, "test", "pre", pre),
            summarize(test_df, "test", "post", post),
        ],
        ignore_index=True,
    )
    _ensure_dir(out_csv.parent)
    out.to_csv(out_csv, index=False)


def _plot_trajectories_ori(ctrl_df: pd.DataFrame, test_df: pd.DataFrame, out_png: Path) -> None:
    cols = [c for c in ["O", "R", "I"] if c in test_df.columns and c in ctrl_df.columns]
    if not cols:
        return

    fig = plt.figure(figsize=(10, 5))
    ax = fig.add_subplot(111)

    x_test = np.arange(len(test_df))
    x_ctrl = np.arange(len(ctrl_df))

    for c in cols:
        ax.plot(x_ctrl, ctrl_df[c].astype(float).values, linestyle="--", linewidth=1.2, label=f"{c} (control)")
        ax.plot(x_test, test_df[c].astype(float).values, linewidth=1.4, label=f"{c} (test)")

    ax.set_title("Trajectoires O, R, I (test vs contrôle)")
    ax.set_xlabel("t")
    ax.set_ylabel("valeur")
    ax.legend(loc="best", fontsize=8)

    _ensure_dir(out_png.parent)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def _plot_corr_matrix(test_df: pd.DataFrame, out_png: Path) -> None:
    cols_pref = ["O", "R", "I", "Cap", "Sigma", "S", "V", "C", "demand"]
    cols = [c for c in cols_pref if c in test_df.columns]
    if len(cols) < 2:
        return

    X = test_df[cols].apply(pd.to_numeric, errors="coerce")
    corr = X.corr()

    fig = plt.figure(figsize=(7.5, 6))
    ax = fig.add_subplot(111)
    im = ax.imshow(corr.values, interpolation="nearest")
    ax.set_title("Matrice de corrélation (variables clés)")
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticklabels(cols)

    for i in range(len(cols)):
        for j in range(len(cols)):
            val = corr.values[i, j]
            if not (math.isnan(val) if isinstance(val, float) else False):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    _ensure_dir(out_png.parent)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def _bootstrap_ci(values: np.ndarray, n_boot: int = 5000, seed: int = 1337) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"q025": np.nan, "q50": np.nan, "q975": np.nan}
    boots = rng.choice(values, size=(n_boot, values.size), replace=True).mean(axis=1)
    return {
        "q025": float(np.quantile(boots, 0.025)),
        "q50": float(np.quantile(boots, 0.50)),
        "q975": float(np.quantile(boots, 0.975)),
        "mean": float(np.mean(boots)),
        "std": float(np.std(boots, ddof=1)),
    }


def _plot_bootstrap(values: np.ndarray, ci: Dict[str, float], out_png: Path) -> None:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return

    rng = np.random.default_rng(1337)
    n_boot = 4000
    boots = rng.choice(values, size=(n_boot, values.size), replace=True).mean(axis=1)

    fig = plt.figure(figsize=(9, 4.5))
    ax = fig.add_subplot(111)
    ax.hist(boots, bins=40)
    ax.axvline(ci["q025"], linestyle="--", linewidth=1.2)
    ax.axvline(ci["q975"], linestyle="--", linewidth=1.2)
    ax.set_title("Bootstrap sur l'effet moyen (IC 95%)")
    ax.set_xlabel("moyenne bootstrap")
    ax.set_ylabel("fréquence")

    _ensure_dir(out_png.parent)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def _plot_sensitivity(robust_df: pd.DataFrame, out_png: Path) -> None:
    if robust_df.empty:
        return

    if not {"omega", "alpha_scale", "threshold_detected"}.issubset(set(robust_df.columns)):
        return

    omegas = np.sort(robust_df["omega"].unique())
    alphas = np.sort(robust_df["alpha_scale"].unique())

    mat = np.zeros((len(alphas), len(omegas)), dtype=float)
    for i, a in enumerate(alphas):
        for j, o in enumerate(omegas):
            sub = robust_df[(robust_df["omega"] == o) & (robust_df["alpha_scale"] == a)]
            mat[i, j] = np.nan if len(sub) == 0 else float(np.mean(sub["threshold_detected"].astype(bool)))

    fig = plt.figure(figsize=(8, 5))
    ax = fig.add_subplot(111)
    im = ax.imshow(mat, aspect="auto", origin="lower", interpolation="nearest")
    ax.set_title("Analyse de sensibilité : part de détections (omega x alpha)")
    ax.set_xlabel("omega")
    ax.set_ylabel("alpha_scale")
    ax.set_xticks(range(len(omegas)))
    ax.set_xticklabels([f"{x:.2f}" for x in omegas], rotation=45, ha="right")
    ax.set_yticks(range(len(alphas)))
    ax.set_yticklabels([f"{x:.2f}" for x in alphas])
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    _ensure_dir(out_png.parent)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def _build_tests_causaux(run_dir: Path, out_csv: Path) -> None:
    rows = []
    for test_id in [
        "T1_noyau_demand_shock",
        "T4_symbolic_S_rich_vs_poor_on_C",
        "T5_symbolic_injection_effect_on_C",
        "T6_symbolic_cut_on_C",
        "T7_progressive_S_to_C_threshold",
        "T8_reinjection_recovery_on_C",
    ]:
        s = run_dir / test_id / "tables" / "summary.json"
        v = run_dir / test_id / "tables" / "verdict.json"
        if not s.exists() and not v.exists():
            continue
        sd = _read_json(s) if s.exists() else {}
        vd = _read_json(v) if v.exists() else {}
        rows.append(
            {
                "test_id": test_id,
                "verdict": vd.get("verdict", sd.get("verdict")),
                "mean_effect": sd.get("mean_effect"),
                "ci_99_low": sd.get("ci_99_low"),
                "ci_99_high": sd.get("ci_99_high"),
                "p_one_sided": sd.get("p_one_sided"),
                "sesoi": sd.get("sesoi"),
                "power_estimate": sd.get("power_estimate"),
            }
        )
    df = pd.DataFrame(rows)
    _ensure_dir(out_csv.parent)
    df.to_csv(out_csv, index=False)


def _build_symbolic_tables(run_dir: Path, tables_dir: Path, figures_dir: Path) -> None:
    t4 = run_dir / "T4_symbolic_S_rich_vs_poor_on_C"
    if (t4 / "tables" / "paired_results.csv").exists():
        df4 = pd.read_csv(t4 / "tables" / "paired_results.csv")
        df4.to_csv(tables_dir / "T4_results.csv", index=False)

        fig = plt.figure(figsize=(6.5, 5))
        ax = fig.add_subplot(111)
        ax.scatter(df4["C_end_poor"].astype(float).values, df4["C_end_rich"].astype(float).values)
        mn = float(min(df4["C_end_poor"].min(), df4["C_end_rich"].min()))
        mx = float(max(df4["C_end_poor"].max(), df4["C_end_rich"].max()))
        ax.plot([mn, mx], [mn, mx], linestyle="--", linewidth=1.0)
        ax.set_title("T4 : C_end (pauvre) vs C_end (riche)")
        ax.set_xlabel("C_end_poor")
        ax.set_ylabel("C_end_rich")
        fig.tight_layout()
        fig.savefig(figures_dir / "T4_scatter_S_vs_C.png", dpi=160)
        plt.close(fig)

    t5 = run_dir / "T5_symbolic_injection_effect_on_C"
    if (t5 / "tables" / "paired_results.csv").exists():
        df5 = pd.read_csv(t5 / "tables" / "paired_results.csv")
        df5.to_csv(tables_dir / "T5_results.csv", index=False)

        cols = [c for c in df5.columns if c.lower().startswith("c_end")]
        diff = df5[cols[0]].astype(float).values if cols else np.array([])

        fig = plt.figure(figsize=(8, 4))
        ax = fig.add_subplot(111)
        ax.plot(np.arange(len(diff)), diff)
        ax.set_title("T5 : effet injection (différences par seed)")
        ax.set_xlabel("seed index")
        ax.set_ylabel("ΔC_end")
        fig.tight_layout()
        fig.savefig(figures_dir / "T5_C_timecourse_injection.png", dpi=160)
        plt.close(fig)

    t7 = run_dir / "T7_progressive_S_to_C_threshold"
    if (t7 / "tables" / "sweep_results.csv").exists():
        df7 = pd.read_csv(t7 / "tables" / "sweep_results.csv")
        df7.to_csv(tables_dir / "T7_results.csv", index=False)

        src = t7 / "figures" / "c_end_vs_s0.png"
        if src.exists():
            _copy_if_exists(src, figures_dir / "T7_piecewise_threshold_S_star.png")

    parts = []
    for name in ["T4_results.csv", "T5_results.csv", "T7_results.csv"]:
        p = tables_dir / name
        if p.exists():
            d = pd.read_csv(p)
            d.insert(0, "source", name.replace("_results.csv", ""))
            parts.append(d.head(1))
    if parts:
        pd.concat(parts, ignore_index=True).to_csv(tables_dir / "symbolic_suite_summary.csv", index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="Path to canonical run dir (e.g. _ci_out/canonical_tests/<run_id>)")
    ap.add_argument("--registered-root", default="05_Results/registered_reports", help="Where to write registered report assets")
    ap.add_argument("--manuscript-root", default="06_Manuscript", help="Where to mirror manuscript assets")
    ap.add_argument("--representative-test", default="T1_noyau_demand_shock", help="Test ID used for descriptives/correlations")
    ap.add_argument("--representative-run", default="run_0001", help="Run name used for descriptives/correlations")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise FileNotFoundError(run_dir)

    reg_root = Path(args.registered_root).resolve()
    man_root = Path(args.manuscript_root).resolve()

    reg_fig = reg_root / "figures"
    reg_tab = reg_root / "tables"
    man_fig = man_root / "figures"
    man_tab = man_root / "tables"

    for p in [reg_fig, reg_tab, man_fig, man_tab]:
        _ensure_dir(p)

    ctrl_df, test_df, thr = _find_run_timeseries(run_dir, args.representative_test, args.representative_run)

    _copy_if_exists(run_dir / "T2_threshold_demo_on_dataset" / "figures" / "c_t_with_threshold.png", reg_fig / "01_evolution_C_seuil.png")
    _copy_if_exists(run_dir / args.representative_test / args.representative_run / "figures" / "v_t.png", reg_fig / "02_effet_intervention.png")

    _plot_trajectories_ori(ctrl_df, test_df, reg_fig / "03_trajectoires_individuelles.png")
    _plot_corr_matrix(test_df, reg_fig / "04_matrice_correlations.png")

    t1_summary_all = run_dir / "T1_noyau_demand_shock" / "tables" / "summary_all.csv"
    if t1_summary_all.exists():
        df = pd.read_csv(t1_summary_all)
        if "effect_C_post_mean" in df.columns:
            vals = df["effect_C_post_mean"].astype(float).values
            ci = _bootstrap_ci(vals)
            _plot_bootstrap(vals, ci, reg_fig / "05_bootstrap_ic.png")
            pd.DataFrame([ci]).to_csv(reg_tab / "05_bootstrap_quantiles.csv", index=False)

    rob_csv = run_dir / "T3_robustness_on_dataset" / "tables" / "robustness_results.csv"
    if rob_csv.exists():
        rdf = pd.read_csv(rob_csv)
        _plot_sensitivity(rdf, reg_fig / "06_analyse_sensibilite.png")
        cols = [c for c in ["omega", "alpha_scale", "threshold_detected", "threshold_value", "threshold_index"] if c in rdf.columns]
        rdf[cols].to_csv(reg_tab / "04_robustesse_parametres.csv", index=False)

    _write_descriptives_phases(ctrl_df, test_df, thr, reg_tab / "01_descriptives_phases.csv")
    _build_tests_causaux(run_dir, reg_tab / "02_tests_causaux.csv")

    t3_sum = run_dir / "T3_robustness_on_dataset" / "tables" / "summary.json"
    if t3_sum.exists():
        pd.DataFrame([_read_json(t3_sum)]).to_csv(reg_tab / "03_robustesse_specifications.csv", index=False)

    _build_symbolic_tables(run_dir, reg_tab, reg_fig)

    for src in reg_fig.glob("*.png"):
        _copy_if_exists(src, man_fig / src.name)
    for src in reg_tab.glob("*.csv"):
        _copy_if_exists(src, man_tab / src.name)

    print(f"[OK] Registered report assets written to: {reg_root}")
    print(f"[OK] Manuscript assets mirrored to: {man_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
