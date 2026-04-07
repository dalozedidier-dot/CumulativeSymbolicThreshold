#!/usr/bin/env python3
"""04_Code/pipeline/run_power_analysis.py

A priori power analysis + maturity classification for each real dataset.

Usage:
  python 04_Code/pipeline/run_power_analysis.py --all --outdir 05_Results/power_analysis/
  python 04_Code/pipeline/run_power_analysis.py --help
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_REPO = Path(__file__).resolve().parents[2]
REAL_DATA_SCRIPT = str(_REPO / "04_Code" / "pipeline" / "run_real_data_demo.py")

SEED = 8000
ALPHA = 0.01


def _discover_datasets(root: Path) -> list[Path]:
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            datasets.append(p.parent)
    return datasets


def _run_oric_get_C(csv_path: Path, outdir: Path) -> np.ndarray | None:
    """Run ORI-C pipeline and extract C(t) series."""
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

    ts_path = outdir / "tables" / "test_timeseries.csv"
    if not ts_path.exists():
        return None
    try:
        df = pd.read_csv(ts_path)
        if "C" in df.columns:
            return pd.to_numeric(df["C"], errors="coerce").fillna(0).values
    except Exception:
        pass
    return None


def cohens_d(pre: np.ndarray, post: np.ndarray) -> float:
    """Cohen's d effect size."""
    n1, n2 = len(pre), len(post)
    if n1 < 2 or n2 < 2:
        return 0.0
    s1, s2 = np.var(pre, ddof=1), np.var(post, ddof=1)
    pooled = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / max(n1 + n2 - 2, 1))
    if pooled < 1e-12:
        return 0.0
    return float((np.mean(post) - np.mean(pre)) / pooled)


def power_analytic(d: float, n: int, alpha: float = ALPHA) -> float:
    """Analytical power for two-sample t-test (equal groups n/2)."""
    n1 = n // 2
    n2 = n - n1
    if n1 < 2 or n2 < 2:
        return 0.0
    se = np.sqrt(1.0 / n1 + 1.0 / n2)
    ncp = abs(d) / se  # non-centrality parameter
    df = n1 + n2 - 2
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    # Power = P(|T| > t_crit | ncp)
    # Use non-central t distribution
    try:
        power = 1.0 - stats.nct.cdf(t_crit, df, ncp) + stats.nct.cdf(-t_crit, df, ncp)
        return float(np.clip(power, 0, 1))
    except Exception:
        return 0.0


def power_bootstrap(pre: np.ndarray, post: np.ndarray,
                    n_boot: int = 500, alpha: float = ALPHA) -> float:
    """Bootstrap power estimation."""
    rng = np.random.default_rng(SEED)
    n1, n2 = len(pre), len(post)
    if n1 < 5 or n2 < 5:
        return 0.0

    detections = 0
    for _ in range(n_boot):
        pre_b = rng.choice(pre, size=n1, replace=True)
        post_b = rng.choice(post, size=n2, replace=True)
        _, p = stats.ttest_ind(post_b, pre_b, equal_var=False)
        if np.isfinite(p) and p < alpha:
            detections += 1

    return float(detections / n_boot)


def n_min_for_power(d: float, target_power: float = 0.90,
                    alpha: float = ALPHA) -> int:
    """Find minimum N for desired power via binary search."""
    if abs(d) < 1e-6:
        return 99999

    lo, hi = 10, 100000
    while lo < hi:
        mid = (lo + hi) // 2
        p = power_analytic(d, mid, alpha)
        if p >= target_power:
            hi = mid
        else:
            lo = mid + 1
    return lo


def classify_power(power: float) -> str:
    """Classify power level."""
    if power >= 0.80:
        return "adequate"
    elif power >= 0.50:
        return "borderline"
    else:
        return "underpowered"


def analyze_dataset(ds_dir: Path, outdir: Path) -> dict:
    """Run power analysis for one dataset."""
    csv_path = ds_dir / "real.csv"
    ds_id = ds_dir.name
    ds_out = outdir / ds_id
    ds_out.mkdir(parents=True, exist_ok=True)

    result = {"dataset_id": ds_id}

    # Get C(t) from ORI-C run
    C = _run_oric_get_C(csv_path, ds_out / "oric_run")
    if C is None or len(C) < 20:
        result["error"] = "Could not extract C(t)"
        result["power_class"] = "underpowered"
        return result

    n = len(C)
    mid = n // 2
    pre = C[:mid]
    post = C[mid:]

    # Effect size
    d = cohens_d(pre, post)
    result["n_total"] = n
    result["n_pre"] = len(pre)
    result["n_post"] = len(post)
    result["effect_size_d"] = float(d)
    result["C_mean_pre"] = float(np.mean(pre))
    result["C_mean_post"] = float(np.mean(post))

    # Analytical power
    pwr_analytic = power_analytic(d, n, ALPHA)
    result["power_analytic"] = float(pwr_analytic)

    # Bootstrap power
    pwr_boot = power_bootstrap(pre, post, n_boot=500, alpha=ALPHA)
    result["power_bootstrap"] = float(pwr_boot)

    # Use max of both
    power_combined = max(pwr_analytic, pwr_boot)
    result["power_combined"] = float(power_combined)
    result["power_class"] = classify_power(power_combined)

    # N minimum for power = 0.90
    n_min = n_min_for_power(d, 0.90, ALPHA)
    result["n_min_for_090"] = n_min
    result["n_sufficient"] = n >= n_min

    # Save
    (ds_out / "power_results.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Power analysis a priori")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=str, default=None)
    ap.add_argument("--outdir", default="05_Results/power_analysis/")
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

    all_results = []
    for i, ds in enumerate(datasets):
        print(f"[{i+1}/{len(datasets)}] {ds.name}...")
        try:
            result = analyze_dataset(ds, outdir)
            all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            all_results.append({"dataset_id": ds.name, "error": str(e), "power_class": "underpowered"})

    # Power report CSV
    if all_results:
        df = pd.DataFrame(all_results)
        cols = ["dataset_id", "n_total", "effect_size_d", "power_analytic",
                "power_bootstrap", "power_combined", "power_class",
                "n_min_for_090", "n_sufficient"]
        available_cols = [c for c in cols if c in df.columns]
        df[available_cols].to_csv(outdir / "power_report.csv", index=False)

    # Markdown report
    lines = ["# Power Analysis Report\n\n"]
    lines.append(f"Alpha = {ALPHA}\n")
    lines.append(f"Datasets: {len(all_results)}\n\n")

    # Summary counts
    classes = {"adequate": 0, "borderline": 0, "underpowered": 0}
    for r in all_results:
        cls = r.get("power_class", "underpowered")
        classes[cls] = classes.get(cls, 0) + 1

    lines.append("## Summary\n\n")
    for cls, count in classes.items():
        lines.append(f"- **{cls}**: {count} datasets\n")

    lines.append("\n## Detail Table\n\n")
    lines.append("| Dataset | N | Cohen's d | Power | Class | N_min(0.90) |\n")
    lines.append("|---------|---|-----------|-------|-------|-------------|\n")
    for r in all_results:
        d = r.get("effect_size_d", "?")
        d_str = f"{d:.3f}" if isinstance(d, float) else str(d)
        p = r.get("power_combined", "?")
        p_str = f"{p:.3f}" if isinstance(p, float) else str(p)
        n_min = r.get("n_min_for_090", "?")
        lines.append(
            f"| {r['dataset_id']} | {r.get('n_total', '?')} | {d_str} "
            f"| {p_str} | {r.get('power_class', '?')} | {n_min} |\n"
        )

    (outdir / "power_report.md").write_text("".join(lines), encoding="utf-8")

    # JSON
    (outdir / "power_results_all.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8")

    n_adequate = classes["adequate"]
    print(f"\nDone. {n_adequate}/{len(all_results)} datasets have adequate power.")
    print(f"Results in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
