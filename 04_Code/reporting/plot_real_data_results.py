#!/usr/bin/env python3
# 04_Code/reporting/plot_real_data_results.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def _find_latest_run_dir(root: Path) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"root not found: {root}")

    candidates = []
    for p in root.rglob("*"):
        if p.is_dir() and (p / "tables" / "test_timeseries.csv").exists():
            candidates.append(p)

    if not candidates:
        candidates = [p for p in root.iterdir() if p.is_dir()]
        if not candidates:
            raise FileNotFoundError(f"no run dirs under: {root}")

    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def _safe_read_json(p: Path) -> dict:
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _plot_series(df: pd.DataFrame, out_png: Path, title: str, cols: list[str]) -> None:
    plt.figure()
    for c in cols:
        if c in df.columns:
            plt.plot(df[c].to_numpy(), label=c)
    plt.title(title)
    plt.xlabel("t (index)")
    plt.ylabel("value")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def _plot_delta(df: pd.DataFrame, out_png: Path, title: str) -> None:
    plt.figure()
    plotted = False
    for c in ["delta_C", "deltaC", "dC"]:
        if c in df.columns:
            plt.plot(df[c].to_numpy(), label=c)
            plotted = True
    plt.title(title)
    plt.xlabel("t (index)")
    plt.ylabel("delta")
    if plotted:
        plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-root", default="_ci_out/real_data_smoke", help="Real-data smoke root directory")
    ap.add_argument("--run-dir", default="", help="Optional explicit run directory")
    args = ap.parse_args()

    real_root = Path(args.real_root)
    run_dir = Path(args.run_dir) if args.run_dir else _find_latest_run_dir(real_root)

    tables = run_dir / "tables"
    figs = run_dir / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    test_csv = tables / "test_timeseries.csv"
    ctrl_csv = tables / "control_timeseries.csv"

    if not test_csv.exists():
        raise FileNotFoundError(f"missing {test_csv}")

    df_test = pd.read_csv(test_csv)
    title_prefix = f"ORI-C real data. run={run_dir.name}"

    # Auto-detect likely column names for C and S
    c_cols = [c for c in df_test.columns if c.lower() in ("c", "c_t", "cap", "capacity", "capacity_proxy")]
    s_cols = [c for c in df_test.columns if c.lower() in ("s", "s_t", "symbolic", "symbolic_proxy")]
    if not c_cols:
        c_cols = [c for c in df_test.columns if c.lower().endswith("_c")]
    if not s_cols:
        s_cols = [c for c in df_test.columns if c.lower().endswith("_s")]

    cols_main = []
    cols_main += c_cols[:1]
    cols_main += s_cols[:1]

    if cols_main:
        _plot_series(df_test, figs / "real_test_series_C_S.png", f"{title_prefix} test series", cols_main)
    else:
        num_cols = [c for c in df_test.columns if pd.api.types.is_numeric_dtype(df_test[c])]
        _plot_series(df_test, figs / "real_test_series_fallback.png", f"{title_prefix} test series (fallback)", num_cols[:2])

    _plot_delta(df_test, figs / "real_test_deltaC.png", f"{title_prefix} delta C (if present)")

    if ctrl_csv.exists():
        df_ctrl = pd.read_csv(ctrl_csv)
        num_cols = [c for c in df_ctrl.columns if pd.api.types.is_numeric_dtype(df_ctrl[c])]
        _plot_series(df_ctrl, figs / "real_control_series.png", f"{title_prefix} control series", num_cols[:2])

    verdict = _safe_read_json(tables / "verdict.json")
    summary = _safe_read_json(tables / "summary.json")

    meta = {
        "run_dir": str(run_dir),
        "figures": [p.name for p in sorted(figs.glob("*.png"))],
        "verdict": verdict,
        "summary": summary,
    }
    (figs / "plot_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Plots written under: {figs}")
    for p in sorted(figs.glob("*.png")):
        print(f"- {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
