#!/usr/bin/env python3
"""04_Code/pipeline/run_proxy_sensitivity.py

Proxy sensitivity analysis (T3b): for each dataset, replace each proxy by
calibrated white noise or an alternative, re-run ORI-C, compare verdict.

Usage:
  python 04_Code/pipeline/run_proxy_sensitivity.py --all --outdir 05_Results/proxy_sensitivity/
  python 04_Code/pipeline/run_proxy_sensitivity.py --dataset 03_Data/real/fred_monthly --outdir 05_Results/proxy_sensitivity/
  python 04_Code/pipeline/run_proxy_sensitivity.py --help
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

SEED = 8000
PROXIES = ["O", "R", "I", "demand", "S"]

REAL_DATA_SCRIPT = str(_REPO / "04_Code" / "pipeline" / "run_real_data_demo.py")
CAUSAL_SCRIPT = str(_REPO / "04_Code" / "pipeline" / "tests_causaux.py")


def _discover_datasets(root: Path) -> list[Path]:
    """Find all directories containing real.csv + proxy_spec.json."""
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            datasets.append(p.parent)
    return datasets


def _generate_calibrated_noise(series: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Generate white noise with same mean, std, and approximate lag-1 autocorrelation."""
    mu = float(np.nanmean(series))
    sigma = float(np.nanstd(series))
    if sigma < 1e-12:
        sigma = 0.1
    # Estimate lag-1 autocorrelation
    s = series[~np.isnan(series)]
    if len(s) > 2:
        rho = float(np.corrcoef(s[:-1], s[1:])[0, 1])
        rho = np.clip(rho, -0.99, 0.99) if np.isfinite(rho) else 0.0
    else:
        rho = 0.0

    n = len(series)
    # AR(1) process: x[t] = rho * x[t-1] + sqrt(1-rho^2) * e[t]
    noise = np.zeros(n)
    noise[0] = rng.normal(0, 1)
    for i in range(1, n):
        noise[i] = rho * noise[i - 1] + np.sqrt(max(1 - rho ** 2, 0.01)) * rng.normal(0, 1)
    # Scale to match mu, sigma
    noise = mu + sigma * (noise - noise.mean()) / max(noise.std(), 1e-12)
    return np.clip(noise, 0.0, 1.0)


def _run_pipeline(csv_path: Path, outdir: Path) -> dict:
    """Run run_real_data_demo.py + tests_causaux.py, return verdict dict."""
    outdir.mkdir(parents=True, exist_ok=True)

    cmd1 = [
        sys.executable, REAL_DATA_SCRIPT,
        "--input", str(csv_path),
        "--outdir", str(outdir),
        "--time-mode", "index",
        "--normalize", "robust",
        "--control-mode", "no_symbolic",
        "--k", "2.5", "--m", "3", "--baseline-n", "50",
    ]
    r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=120)

    verdict = {"verdict": "ERROR", "pipeline_rc": r1.returncode}
    summary_path = outdir / "tables" / "summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text())
            verdict["pipeline_verdict"] = summary.get("verdict", "UNKNOWN")
        except Exception:
            pass

    # Run causal tests
    cmd2 = [
        sys.executable, CAUSAL_SCRIPT,
        "--run-dir", str(outdir),
        "--alpha", "0.01",
    ]
    r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
    verdict["causal_rc"] = r2.returncode

    verdict_path = outdir / "tables" / "verdict.json"
    if verdict_path.exists():
        try:
            v = json.loads(verdict_path.read_text())
            verdict["verdict"] = v.get("verdict", "UNKNOWN")
            verdict["p_value"] = v.get("p_value_C_mean_shift", None)
        except Exception:
            pass
    elif "pipeline_verdict" in verdict:
        verdict["verdict"] = verdict["pipeline_verdict"]

    return verdict


def run_sensitivity_for_dataset(dataset_dir: Path, outdir: Path, seed: int) -> dict:
    """Run sensitivity analysis for one dataset."""
    csv_path = dataset_dir / "real.csv"
    df = pd.read_csv(csv_path)
    rng = np.random.default_rng(seed)

    dataset_id = dataset_dir.name
    results = {"dataset_id": dataset_id, "dataset_path": str(dataset_dir)}

    # 1. Original verdict
    orig_dir = outdir / dataset_id / "original"
    orig_verdict = _run_pipeline(csv_path, orig_dir)
    results["original_verdict"] = orig_verdict.get("verdict", "ERROR")

    # 2. For each proxy, replace with noise
    sensitivity = {}
    for proxy in PROXIES:
        if proxy not in df.columns:
            sensitivity[proxy] = {
                "noise_verdict": "SKIP",
                "necessary": None,
                "note": f"Column {proxy} not in dataset"
            }
            continue

        # Replace proxy with calibrated noise
        df_noise = df.copy()
        original_vals = df[proxy].values.astype(float)
        df_noise[proxy] = _generate_calibrated_noise(original_vals, rng)

        # Save to temp CSV
        noise_csv = outdir / dataset_id / f"noise_{proxy}" / "input.csv"
        noise_csv.parent.mkdir(parents=True, exist_ok=True)
        df_noise.to_csv(noise_csv, index=False)

        noise_run_dir = outdir / dataset_id / f"noise_{proxy}" / "run"
        noise_verdict = _run_pipeline(noise_csv, noise_run_dir)

        orig_v = results["original_verdict"]
        noise_v = noise_verdict.get("verdict", "ERROR")

        # Determine if proxy is necessary
        if orig_v == "ACCEPT" and noise_v in ("REJECT", "NOT_DETECTED", "INDETERMINATE"):
            necessary = True
            note = f"Noise replacement changes verdict {orig_v} -> {noise_v}: proxy is NECESSARY"
        elif orig_v == "ACCEPT" and noise_v == "ACCEPT":
            necessary = False
            note = f"Noise replacement keeps verdict ACCEPT: proxy may be REDUNDANT"
        else:
            necessary = None
            note = f"Original={orig_v}, Noise={noise_v}: sensitivity unclear"

        sensitivity[proxy] = {
            "noise_verdict": noise_v,
            "necessary": necessary,
            "note": note,
        }

    results["sensitivity"] = sensitivity
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Proxy sensitivity analysis (T3b)")
    ap.add_argument("--all", action="store_true", help="Run on all discovered datasets")
    ap.add_argument("--dataset", type=str, default=None, help="Path to a specific dataset directory")
    ap.add_argument("--outdir", default="05_Results/proxy_sensitivity/", help="Output directory")
    ap.add_argument("--seed", type=int, default=SEED, help="Base seed")
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
        print(f"\n[{i+1}/{len(datasets)}] Processing {ds.name}...")
        try:
            result = run_sensitivity_for_dataset(ds, outdir, args.seed + i)
            all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            all_results.append({"dataset_id": ds.name, "error": str(e)})

    # Generate sensitivity matrix CSV
    rows = []
    for r in all_results:
        if "sensitivity" not in r:
            continue
        for proxy, info in r["sensitivity"].items():
            rows.append({
                "dataset_id": r["dataset_id"],
                "proxy": proxy,
                "original_verdict": r.get("original_verdict", "?"),
                "noise_verdict": info.get("noise_verdict", "?"),
                "necessary": info.get("necessary"),
                "note": info.get("note", ""),
            })

    if rows:
        df_matrix = pd.DataFrame(rows)
        df_matrix.to_csv(outdir / "sensitivity_matrix.csv", index=False)

    # Generate markdown report
    report_lines = ["# Proxy Sensitivity Report (T3b)\n"]
    report_lines.append(f"Date: auto-generated\n")
    report_lines.append(f"Datasets analyzed: {len(all_results)}\n")
    report_lines.append(f"Seed: {args.seed}\n\n")

    report_lines.append("## Summary Matrix\n\n")
    report_lines.append("| Dataset | Proxy | Original | Noise | Necessary? |\n")
    report_lines.append("|---------|-------|----------|-------|------------|\n")
    for row in rows:
        nec = "YES" if row["necessary"] is True else ("NO" if row["necessary"] is False else "?")
        report_lines.append(
            f"| {row['dataset_id']} | {row['proxy']} | {row['original_verdict']} "
            f"| {row['noise_verdict']} | {nec} |\n"
        )

    report_lines.append("\n## Interpretation\n\n")
    report_lines.append("- **Necessary**: replacing proxy with noise changes ACCEPT -> non-ACCEPT\n")
    report_lines.append("- **Redundant**: replacing proxy with noise keeps ACCEPT\n")
    report_lines.append("- **Unclear**: original verdict was not ACCEPT\n")

    (outdir / "sensitivity_report.md").write_text("".join(report_lines), encoding="utf-8")

    # Save full JSON results
    (outdir / "sensitivity_results.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )

    print(f"\nDone. Results in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
