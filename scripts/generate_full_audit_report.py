#!/usr/bin/env python3
"""scripts/generate_full_audit_report.py

Aggregate all results from Blocs 1-7 into a single synthesis report.

Usage:
  python scripts/generate_full_audit_report.py --outdir 05_Results/
  python scripts/generate_full_audit_report.py --help
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def _load_json(path: Path) -> dict | list | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _load_csv(path: Path) -> pd.DataFrame | None:
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    return None


def _discover_datasets(root: Path) -> list[dict]:
    """Discover all datasets with real.csv + proxy_spec.json."""
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            spec = _load_json(p.parent / "proxy_spec.json")
            df = pd.read_csv(p, nrows=5)
            datasets.append({
                "path": str(p.parent),
                "id": p.parent.name,
                "sector": spec.get("sector", "unknown") if spec else "unknown",
                "n": len(pd.read_csv(p)),
            })
    return datasets


def generate_report(results_dir: Path, data_dir: Path) -> str:
    """Generate the full synthesis report as markdown."""
    lines = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines.append("# ORI-C Full Real Data Audit Report\n\n")
    lines.append(f"Generated: {now}\n\n")
    lines.append("---\n\n")

    # ── Section 1: Dataset inventory ──
    lines.append("## 1. Dataset Inventory\n\n")
    datasets = _discover_datasets(data_dir)
    lines.append(f"Total datasets found: **{len(datasets)}**\n\n")
    lines.append("| # | Dataset ID | Sector | N |\n")
    lines.append("|---|-----------|--------|---|\n")
    for i, ds in enumerate(datasets, 1):
        lines.append(f"| {i} | {ds['id']} | {ds['sector']} | {ds['n']} |\n")
    lines.append("\n")

    # ── Section 2: Proxy sensitivity ──
    lines.append("## 2. Proxy Sensitivity Matrix (T3b)\n\n")
    sens_csv = _load_csv(results_dir / "proxy_sensitivity" / "sensitivity_matrix.csv")
    if sens_csv is not None and len(sens_csv) > 0:
        lines.append(f"Proxies tested: {len(sens_csv)} entries\n\n")
        lines.append("| Dataset | Proxy | Original | Noise | Necessary |\n")
        lines.append("|---------|-------|----------|-------|----------|\n")
        for _, row in sens_csv.iterrows():
            nec = "YES" if row.get("necessary") is True else (
                "NO" if row.get("necessary") is False else "?")
            lines.append(
                f"| {row.get('dataset_id', '?')} | {row.get('proxy', '?')} "
                f"| {row.get('original_verdict', '?')} | {row.get('noise_verdict', '?')} "
                f"| {nec} |\n")
    else:
        lines.append("*No proxy sensitivity results available. Run run_proxy_sensitivity.py first.*\n")
    lines.append("\n")

    # ── Section 3: Model comparison V1/V2/V3/V4 ──
    lines.append("## 3. Model Comparison (V1/V2/V3/V4)\n\n")
    comp_csv = _load_csv(results_dir / "model_comparison" / "comparison_table.csv")
    if comp_csv is not None and len(comp_csv) > 0:
        lines.append(f"Variants compared across {comp_csv['dataset_id'].nunique()} datasets\n\n")
        lines.append("| Dataset | Variant | Verdict | Effect Size d | C Mean |\n")
        lines.append("|---------|---------|---------|---------------|--------|\n")
        for _, row in comp_csv.iterrows():
            d = f"{row.get('effect_size_d', 0):.3f}" if pd.notna(row.get("effect_size_d")) else "?"
            cm = f"{row.get('C_mean', 0):.3f}" if pd.notna(row.get("C_mean")) else "?"
            lines.append(
                f"| {row.get('dataset_id', '?')} | {row.get('variant', '?')} "
                f"| {row.get('verdict', '?')} | {d} | {cm} |\n")
    else:
        lines.append("*No model comparison results. Run run_model_comparison.py first.*\n")
    lines.append("\n")

    # ── Section 4: Benchmark ORI-C vs alternatives ──
    lines.append("## 4. Comparative Benchmark\n\n")
    bench_csv = _load_csv(results_dir / "comparative_benchmark" / "benchmark_table.csv")
    if bench_csv is not None and len(bench_csv) > 0:
        n_ds = bench_csv["dataset_id"].nunique()
        n_methods = bench_csv["method"].nunique()
        lines.append(f"{n_ds} datasets x {n_methods} methods\n\n")

        # Summary: detection rate by method
        summary = bench_csv.groupby("method")["detected"].mean()
        lines.append("### Detection Rate by Method\n\n")
        lines.append("| Method | Detection Rate |\n")
        lines.append("|--------|---------------|\n")
        for method, rate in summary.items():
            lines.append(f"| {method} | {rate:.1%} |\n")

        # ORI-C unique detections
        oric_unique = 0
        for ds_id in bench_csv["dataset_id"].unique():
            ds_df = bench_csv[bench_csv["dataset_id"] == ds_id]
            oric = ds_df[ds_df["method"] == "oric"]["detected"].values
            others = ds_df[ds_df["method"] != "oric"]["detected"].values
            if len(oric) and oric[0] and not any(others):
                oric_unique += 1
        lines.append(f"\nORI-C unique detections: **{oric_unique}** datasets\n")
    else:
        lines.append("*No benchmark results. Run run_comparative_benchmark_full.py first.*\n")
    lines.append("\n")

    # ── Section 5: Causal inference ──
    lines.append("## 5. Causal Inference Results\n\n")
    causal_json = _load_json(results_dir / "causal_inference" / "causal_results_all.json")
    if causal_json and isinstance(causal_json, list):
        lines.append(f"Datasets analyzed: {len(causal_json)}\n\n")
        lines.append("| Dataset | CCM Dir | TE Dir | DAG OK | DiD Events |\n")
        lines.append("|---------|---------|--------|--------|------------|\n")
        for r in causal_json:
            ccm = r.get("ccm", {}).get("ccm_direction", "?")
            te = r.get("transfer_entropy", {}).get("te_direction", "?")
            dag = r.get("dag", {}).get("dag_consistent", "?")
            did = r.get("natural_experiment", {}).get("events_tested", 0)
            lines.append(f"| {r.get('dataset_id', '?')} | {ccm} | {te} | {dag} | {did} |\n")
    else:
        lines.append("*No causal inference results. Run run_causal_inference.py first.*\n")
    lines.append("\n")

    # ── Section 6: Multi-scale coherence ──
    lines.append("## 6. Multi-Scale Coherence\n\n")
    ms_csv = _load_csv(results_dir / "multiscale" / "multiscale_coherence.csv")
    if ms_csv is not None and len(ms_csv) > 0:
        n_ds = ms_csv["dataset_id"].nunique()
        coherent = ms_csv.groupby("dataset_id")["verdict"].apply(
            lambda x: len(set(v for v in x if v not in ("SKIP", "ERROR"))) <= 1)
        n_coh = coherent.sum()
        lines.append(f"Cross-scale coherent: **{n_coh}/{n_ds}** datasets\n\n")
        lines.append("| Dataset | Scale | N | Verdict |\n")
        lines.append("|---------|-------|---|--------|\n")
        for _, row in ms_csv.iterrows():
            lines.append(
                f"| {row.get('dataset_id', '?')} | {row.get('scale', '?')} "
                f"| {row.get('n', '?')} | {row.get('verdict', '?')} |\n")
    else:
        lines.append("*No multiscale results. Run run_multiscale.py first.*\n")
    lines.append("\n")

    # ── Section 7: Power analysis ──
    lines.append("## 7. Power Analysis\n\n")
    pwr_csv = _load_csv(results_dir / "power_analysis" / "power_report.csv")
    if pwr_csv is not None and len(pwr_csv) > 0:
        classes = pwr_csv["power_class"].value_counts() if "power_class" in pwr_csv.columns else {}
        for cls, n in classes.items():
            lines.append(f"- **{cls}**: {n} datasets\n")
        lines.append("\n")
        lines.append("| Dataset | N | Cohen's d | Power | Class |\n")
        lines.append("|---------|---|-----------|-------|-------|\n")
        for _, row in pwr_csv.iterrows():
            d = f"{row.get('effect_size_d', 0):.3f}" if pd.notna(row.get("effect_size_d")) else "?"
            p = f"{row.get('power_combined', 0):.3f}" if pd.notna(row.get("power_combined")) else "?"
            lines.append(
                f"| {row.get('dataset_id', '?')} | {row.get('n_total', '?')} "
                f"| {d} | {p} | {row.get('power_class', '?')} |\n")
    else:
        lines.append("*No power analysis results. Run run_power_analysis.py first.*\n")
    lines.append("\n")

    # ── Section 8: Global verdict ──
    lines.append("## 8. Global Verdict\n\n")

    n_total = len(datasets)
    # Count ACCEPT from power report or benchmark
    n_accept = 0
    n_adequate = 0
    if pwr_csv is not None and "power_class" in pwr_csv.columns:
        n_adequate = int((pwr_csv["power_class"] == "adequate").sum())
    if bench_csv is not None:
        oric_rows = bench_csv[bench_csv["method"] == "oric"]
        n_accept = int(oric_rows["detected"].sum())

    lines.append(f"- Total datasets: **{n_total}**\n")
    lines.append(f"- ORI-C ACCEPT: **{n_accept}** (from benchmark)\n")
    lines.append(f"- Power adequate: **{n_adequate}** (from power analysis)\n")

    if n_total > 0:
        lines.append(f"\n**Verdict: {n_accept}/{n_total} datasets ACCEPT with "
                      f"{n_adequate} having adequate power.**\n")

    lines.append("\n---\n")
    lines.append(f"\n*Report generated by scripts/generate_full_audit_report.py*\n")
    lines.append(f"*Seed base: 8000 | Alpha: 0.01 | Framework: ORI-C v1.3*\n")

    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate full audit report")
    ap.add_argument("--outdir", default="05_Results/", help="Results root directory")
    ap.add_argument("--datadir", default="03_Data/", help="Data root directory")
    args = ap.parse_args()

    results_dir = Path(args.outdir)
    data_dir = Path(args.datadir)

    report = generate_report(results_dir, data_dir)

    out_path = results_dir / "FULL_REAL_DATA_REPORT.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}")
    print(f"Length: {len(report)} chars, {report.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
