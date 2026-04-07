#!/usr/bin/env python3
"""04_Code/pipeline/run_comparative_benchmark_full.py

Systematic benchmark: ORI-C vs CUSUM, structural break, z-score, EWS, Bai-Perron.
Runs on all real datasets and placebo battery.

Usage:
  python 04_Code/pipeline/run_comparative_benchmark_full.py --all --outdir 05_Results/comparative_benchmark/
  python 04_Code/pipeline/run_comparative_benchmark_full.py --help
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_CODE = Path(__file__).resolve().parents[1]
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from oric.comparative_benchmark import (  # noqa: E402
    MethodResult, BenchmarkComparison,
    cusum_changepoint, structural_break, anomaly_zscore, early_warning_signal,
)

SEED = 8000
REAL_DATA_SCRIPT = str(_REPO / "04_Code" / "pipeline" / "run_real_data_demo.py")


# ── Additional methods ────────────────────────────────────────────────────

def bai_perron_ruptures(series: np.ndarray, n_bkps: int = 3) -> MethodResult:
    """Bai-Perron via ruptures library (if available), else manual PELT-like."""
    try:
        import ruptures as rpt
        algo = rpt.Pelt(model="rbf", min_size=max(10, len(series) // 20))
        result = algo.fit_predict(series.reshape(-1, 1), pen=np.log(len(series)) * np.var(series))
        bkps = [b for b in result if b < len(series)]
        detected = len(bkps) > 0
        detection_point = int(bkps[0]) if bkps else None
        return MethodResult(
            method="bai_perron",
            detected=detected,
            detection_point=detection_point,
            statistic=float(len(bkps)),
            p_value=None,
            confidence="high" if len(bkps) >= 2 else "medium",
            notes=f"ruptures PELT, breakpoints={bkps[:5]}",
        )
    except ImportError:
        return _manual_pelt(series, n_bkps)


def _manual_pelt(series: np.ndarray, n_bkps: int = 3) -> MethodResult:
    """Manual binary segmentation changepoint detection (no ruptures)."""
    n = len(series)
    if n < 20:
        return MethodResult(method="bai_perron", detected=False, notes="Too short")

    # Binary segmentation: find best split recursively
    def _cost(seg):
        if len(seg) < 2:
            return 0.0
        return float(np.var(seg) * len(seg))

    def _best_split(seg, offset):
        if len(seg) < 10:
            return None, 0.0
        best_gain = 0.0
        best_idx = None
        total_cost = _cost(seg)
        for i in range(5, len(seg) - 5):
            cost_split = _cost(seg[:i]) + _cost(seg[i:])
            gain = total_cost - cost_split
            if gain > best_gain:
                best_gain = gain
                best_idx = offset + i
        return best_idx, best_gain

    breakpoints = []
    segments = [(0, n)]
    for _ in range(n_bkps):
        best_global_gain = 0
        best_global_idx = None
        best_seg_i = None
        for si, (start, end) in enumerate(segments):
            idx, gain = _best_split(series[start:end], start)
            if idx is not None and gain > best_global_gain:
                best_global_gain = gain
                best_global_idx = idx
                best_seg_i = si
        if best_global_idx is None:
            break
        breakpoints.append(best_global_idx)
        s, e = segments[best_seg_i]
        segments.pop(best_seg_i)
        segments.insert(best_seg_i, (s, best_global_idx))
        segments.insert(best_seg_i + 1, (best_global_idx, e))

    breakpoints.sort()
    detected = len(breakpoints) > 0

    # Significance test via permutation
    if detected:
        orig_cost = sum(_cost(series[s:e]) for s, e in segments)
        rng = np.random.default_rng(SEED)
        n_perm = 200
        count = 0
        for _ in range(n_perm):
            perm = rng.permutation(series)
            perm_cost = _cost(perm)
            if perm_cost <= orig_cost:
                count += 1
        p_val = count / n_perm
    else:
        p_val = 1.0

    return MethodResult(
        method="bai_perron",
        detected=detected and p_val < 0.05,
        detection_point=int(breakpoints[0]) if breakpoints else None,
        statistic=float(len(breakpoints)),
        p_value=float(p_val),
        confidence="high" if p_val < 0.01 else ("medium" if p_val < 0.05 else "low"),
        notes=f"manual binary segmentation, breakpoints={breakpoints[:5]}",
    )


def _run_oric_on_csv(csv_path: Path, outdir: Path) -> dict:
    """Run ORI-C pipeline and return verdict info."""
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, REAL_DATA_SCRIPT,
        "--input", str(csv_path),
        "--outdir", str(outdir),
        "--time-mode", "index",
        "--normalize", "robust",
        "--control-mode", "no_symbolic",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    summary_path = outdir / "tables" / "summary.json"
    verdict = "ERROR"
    hit_idx = None
    if summary_path.exists():
        s = json.loads(summary_path.read_text())
        verdict = s.get("verdict", "ERROR")
        hit_idx = s.get("threshold_hit_idx")

    return {"verdict": verdict, "detection_point": hit_idx}


def _robust_minmax(x):
    x = np.asarray(x, dtype=float)
    f = np.isfinite(x)
    if not f.any():
        return np.zeros_like(x)
    lo, hi = np.quantile(x[f], 0.02), np.quantile(x[f], 0.98)
    if abs(hi - lo) < 1e-12:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0, 1)


def _discover_datasets(root: Path) -> list[Path]:
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            datasets.append(p.parent)
    return datasets


def benchmark_dataset(ds_dir: Path, outdir: Path) -> list[dict]:
    """Run all methods on one dataset. Return list of row dicts."""
    csv_path = ds_dir / "real.csv"
    df = pd.read_csv(csv_path)
    ds_id = ds_dir.name

    # Build delta_C series for competing methods
    # Use C if available, otherwise use a proxy: cumsum of S weighted
    if "C" in df.columns:
        series = df["C"].values.astype(float)
    elif "S" in df.columns:
        series = np.nancumsum(pd.to_numeric(df["S"], errors="coerce").fillna(0).values)
    else:
        series = np.zeros(len(df))

    series = np.nan_to_num(series, nan=0.0)
    delta_series = np.diff(series, prepend=0.0)

    results = []

    # 1. ORI-C
    oric_dir = outdir / ds_id / "oric_run"
    oric_info = _run_oric_on_csv(csv_path, oric_dir)
    results.append({
        "dataset_id": ds_id, "method": "oric",
        "detected": oric_info["verdict"] == "ACCEPT",
        "detection_point": oric_info["detection_point"],
        "verdict": oric_info["verdict"],
        "p_value": None, "statistic": None,
    })

    # 2. CUSUM
    r = cusum_changepoint(delta_series)
    results.append({
        "dataset_id": ds_id, "method": "cusum",
        "detected": r.detected, "detection_point": r.detection_point,
        "verdict": "DETECTED" if r.detected else "NOT_DETECTED",
        "p_value": r.p_value, "statistic": r.statistic,
    })

    # 3. Structural break
    r = structural_break(series)
    results.append({
        "dataset_id": ds_id, "method": "structural_break",
        "detected": r.detected, "detection_point": r.detection_point,
        "verdict": "DETECTED" if r.detected else "NOT_DETECTED",
        "p_value": r.p_value, "statistic": r.statistic,
    })

    # 4. Anomaly z-score
    r = anomaly_zscore(delta_series)
    results.append({
        "dataset_id": ds_id, "method": "anomaly_zscore",
        "detected": r.detected, "detection_point": r.detection_point,
        "verdict": "DETECTED" if r.detected else "NOT_DETECTED",
        "p_value": r.p_value, "statistic": r.statistic,
    })

    # 5. Early Warning Signal
    r = early_warning_signal(series)
    results.append({
        "dataset_id": ds_id, "method": "early_warning",
        "detected": r.detected, "detection_point": r.detection_point,
        "verdict": "DETECTED" if r.detected else "NOT_DETECTED",
        "p_value": r.p_value, "statistic": r.statistic,
    })

    # 6. Bai-Perron
    r = bai_perron_ruptures(series)
    results.append({
        "dataset_id": ds_id, "method": "bai_perron",
        "detected": r.detected, "detection_point": r.detection_point,
        "verdict": "DETECTED" if r.detected else "NOT_DETECTED",
        "p_value": r.p_value, "statistic": r.statistic,
    })

    # Generate detection overlay figure
    figdir = outdir / ds_id / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    t = np.arange(len(series))
    ax.plot(t, series, "k-", alpha=0.5, label="series")
    colors = {"oric": "blue", "cusum": "orange", "structural_break": "green",
              "anomaly_zscore": "red", "early_warning": "purple", "bai_perron": "brown"}
    for row in results:
        if row["detection_point"] is not None:
            ax.axvline(row["detection_point"], color=colors.get(row["method"], "gray"),
                       linestyle="--", alpha=0.7, label=f"{row['method']} ({row['detection_point']})")
    ax.set_title(f"{ds_id} — Detection Points by Method")
    ax.legend(fontsize=8)
    ax.set_xlabel("t")
    plt.tight_layout()
    plt.savefig(figdir / "detection_overlay.png", dpi=160)
    plt.close()

    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Systematic comparative benchmark")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=str, default=None)
    ap.add_argument("--outdir", default="05_Results/comparative_benchmark/")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.dataset:
        datasets = [Path(args.dataset)]
    elif args.all:
        datasets = _discover_datasets(_REPO / "03_Data")
    else:
        ap.print_help()
        return 1

    print(f"Found {len(datasets)} datasets")

    all_rows = []
    for i, ds in enumerate(datasets):
        print(f"[{i+1}/{len(datasets)}] {ds.name}...")
        try:
            rows = benchmark_dataset(ds, outdir)
            all_rows.extend(rows)
        except Exception as e:
            print(f"  ERROR: {e}")

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(outdir / "benchmark_table.csv", index=False)

        # Markdown summary
        lines = ["# Comparative Benchmark Summary\n\n"]
        lines.append("| Dataset | Method | Detected | Detection Point | p-value |\n")
        lines.append("|---------|--------|----------|-----------------|----------|\n")
        for _, row in df.iterrows():
            p = f"{row['p_value']:.4f}" if pd.notna(row['p_value']) else "N/A"
            dp = str(row['detection_point']) if pd.notna(row['detection_point']) else "N/A"
            lines.append(f"| {row['dataset_id']} | {row['method']} | {row['detected']} | {dp} | {p} |\n")

        # ORI-C unique detections
        lines.append("\n## ORI-C Unique Detections\n\n")
        for ds_id in df["dataset_id"].unique():
            ds_df = df[df["dataset_id"] == ds_id]
            oric_detected = ds_df[ds_df["method"] == "oric"]["detected"].values
            others_detected = ds_df[ds_df["method"] != "oric"]["detected"].values
            if len(oric_detected) and oric_detected[0] and not any(others_detected):
                lines.append(f"- **{ds_id}**: ORI-C detects transition, others do not\n")

        (outdir / "benchmark_summary.md").write_text("".join(lines), encoding="utf-8")

    print(f"\nDone. Results in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
