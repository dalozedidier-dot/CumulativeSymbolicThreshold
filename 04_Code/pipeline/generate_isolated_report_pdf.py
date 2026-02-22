#!/usr/bin/env python3
"""generate_isolated_report_pdf.py

Generate a multi-page PDF from isolated T1..T8 test results.

Expected directory layout (produced by nightly_isolated.yml after reorganisation):
    <run_dir>/
        global_summary.json
        T1_noyau_demand_shock/
            manifest.json
            seed_table.csv
            verdict.txt
            tables/verdict.json
            tables/summary.json   (statistical tests only)
        T2_threshold_demo_on_dataset/
            ...
        ...

Output: <run_dir>/isolated_proof_report.pdf  (9 pages: 1 cover + 1 per test)

Usage:
    python 04_Code/pipeline/generate_isolated_report_pdf.py \\
        --run-dir 05_Results/isolated_tests/<RUN_ID> \\
        --out     05_Results/isolated_tests/<RUN_ID>/isolated_proof_report.pdf
"""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


ORDERED_TESTS = [
    ("T1", "T1_noyau_demand_shock"),
    ("T2", "T2_threshold_demo_on_dataset"),
    ("T3", "T3_robustness_on_dataset"),
    ("T4", "T4_symbolic_S_rich_vs_poor_on_C"),
    ("T5", "T5_symbolic_injection_effect_on_C"),
    ("T6", "T6_symbolic_cut_on_C"),
    ("T7", "T7_progressive_S_to_C_threshold"),
    ("T8", "T8_reinjection_recovery_on_C"),
]

# Decisional fields to extract (in display order).
# Each entry: (json_key, display_label)
DISPLAY_FIELDS: list[tuple[str, str]] = [
    ("p_value",                 "p-value"),
    ("p_value_welch",           "p-value (Welch)"),
    ("p_hat",                   "p_hat (bootstrap)"),
    ("p_ok",                    "p_ok"),
    ("ci_99_low",               "CI 99% low"),
    ("ci_99_high",              "CI 99% high"),
    ("ci_ok",                   "ci_ok"),
    ("sesoi_ok",                "SESOI ok"),
    ("power_estimate",          "power estimate"),
    ("power_ok",                "power_ok"),
    ("effect_sd",               "effect size (SD)"),
    ("delta_C_end",             "delta_C_end"),
    ("share_threshold_detected","share detected"),
    ("threshold_S0",            "threshold S0"),
    ("threshold_detected",      "threshold detected"),
    ("threshold_value",         "threshold value"),
    ("n",                       "n (scenarios)"),
    ("n_runs_total",            "n_runs_total"),
    ("n_runs",                  "n_runs"),
]

# Palette
C_DARK   = "#2c3e50"
C_ACCEPT = "#1a7a1a"
C_REJECT = "#b00000"
C_INDET  = "#8a6800"
C_BG_OK  = "#e8f5e9"
C_BG_WARN = "#fff8e1"
C_BG_ERR = "#ffebee"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _verdict_color(v: str) -> str:
    if v == "ACCEPT":
        return C_ACCEPT
    if v == "REJECT":
        return C_REJECT
    return C_INDET


def _verdict_bg(v: str) -> str:
    if v == "ACCEPT":
        return C_BG_OK
    if v == "REJECT":
        return C_BG_ERR
    return C_BG_WARN


def _fmt_val(val: object) -> str:
    if isinstance(val, float):
        return f"{val:.5g}"
    if isinstance(val, bool):
        return "True" if val else "False"
    return str(val)


# ── Page 1: Cover ─────────────────────────────────────────────────────────────

def _page_cover(pdf: PdfPages, gsum: dict, run_id: str, timestamp: str) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    # Title
    ax.text(0.5, 0.97, "ORI-C — Isolated T1..T8 Proof Report",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=16, fontweight="bold", color=C_DARK)

    # Run metadata
    meta = [
        f"Run ID      : {run_id}",
        f"Timestamp   : {timestamp}",
        f"Base seed   : {gsum.get('base_seed', '?')}",
        f"Seed strategy : {gsum.get('seed_strategy', 'distinct per-test seeds (base+offset)')}",
        f"run_mode    : {gsum.get('run_mode', '?')}",
        f"N_min       : {gsum.get('N_min', 50)}",
        f"Commit SHA  : {str(gsum.get('commit_sha', 'unknown'))[:16]}",
    ]
    y = 0.90
    for line in meta:
        ax.text(0.05, y, line, transform=ax.transAxes, va="top",
                fontsize=9, family="monospace", color="#444444")
        y -= 0.025

    # Global result banner
    n_accept = gsum.get("n_accept", 0)
    n_reject = gsum.get("n_reject", 0)
    n_indet  = gsum.get("n_indeterminate", 0)
    all_ok   = gsum.get("all_8_accept", False)
    banner   = f"{n_accept}/8 ACCEPT" + (f"  |  {n_reject} REJECT" if n_reject else "") + (f"  |  {n_indet} INDETERMINATE" if n_indet else "")
    b_color  = C_ACCEPT if all_ok else C_REJECT if n_reject else C_INDET
    b_bg     = C_BG_OK  if all_ok else C_BG_ERR if n_reject else C_BG_WARN

    ax.text(0.5, 0.68, banner,
            transform=ax.transAxes, ha="center", va="top",
            fontsize=22, fontweight="bold", color=b_color,
            bbox=dict(boxstyle="round,pad=0.4", fc=b_bg, ec=b_color, lw=2))

    seeds_ok  = gsum.get("seeds_distinct", False)
    fields_ok = gsum.get("all_fields_present", False)
    ax.text(0.5, 0.60,
            f"Seeds distinct: {'OK' if seeds_ok else 'FAIL'}   "
            f"All fields present: {'OK' if fields_ok else 'FAIL'}",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=10,
            color=C_ACCEPT if (seeds_ok and fields_ok) else C_REJECT)

    # Per-test summary table
    tests = gsum.get("tests", {})
    rows = []
    for short, _ in ORDERED_TESTS:
        t = tests.get(short, {})
        rows.append([
            short,
            str(t.get("seed", "?")),
            str(t.get("seed_formula", "?")),
            str(t.get("n_runs", "?")),
            str(t.get("test_type", "?")),
            str(t.get("run_mode", "?")),
            str(t.get("verdict", "MISSING")),
        ])

    table = ax.table(
        cellText=rows,
        colLabels=["Test", "Seed", "Formula", "n_runs", "Type", "Mode", "Verdict"],
        loc="center",
        cellLoc="center",
        bbox=[0.0, 0.07, 1.0, 0.47],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor(C_DARK)
            cell.set_text_props(color="white", fontweight="bold")
        else:
            v = rows[row - 1][6] if row - 1 < len(rows) else ""
            if col == 6:
                cell.set_facecolor(_verdict_bg(v))
                cell.set_text_props(color=_verdict_color(v), fontweight="bold")
            else:
                cell.set_facecolor("#f5f5f5" if row % 2 == 0 else "white")

    # Forbidden labels footer
    ax.text(0.5, 0.02,
            "FORBIDDEN IN ANY REPORT: 'full support'  |  'full empirical support'",
            transform=ax.transAxes, ha="center", fontsize=8,
            color=C_REJECT, style="italic")

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── Pages 2–9: one per test ────────────────────────────────────────────────────

def _page_test(pdf: PdfPages, short: str, test_id: str, test_dir: Path) -> None:
    manifest  = _load_json(test_dir / "manifest.json")
    verdict_j = _load_json(test_dir / "tables" / "verdict.json")
    summary_j = _load_json(test_dir / "tables" / "summary.json")

    # Merged data (verdict.json takes precedence for the verdict field; summary.json for stats)
    data = {**verdict_j, **summary_j}

    verdict    = manifest.get("verdict", data.get("verdict", "UNKNOWN"))
    test_type  = manifest.get("test_type", "?")
    run_mode   = manifest.get("run_mode", "?")
    seed       = manifest.get("seed", "?")
    sf         = manifest.get("seed_formula", "?")
    n_runs     = manifest.get("n_runs", "?")
    dataset_id = manifest.get("dataset_id", "?")
    commit_sha = str(manifest.get("commit_sha", "?"))[:16]

    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    # Header bar
    ax.text(0.05, 0.97, f"{short}  —  {test_id}",
            transform=ax.transAxes, va="top",
            fontsize=13, fontweight="bold", color=C_DARK)

    ax.text(0.80, 0.97, verdict,
            transform=ax.transAxes, ha="center", va="top",
            fontsize=20, fontweight="bold", color=_verdict_color(verdict),
            bbox=dict(boxstyle="round,pad=0.35",
                      fc=_verdict_bg(verdict), ec=_verdict_color(verdict), lw=1.5))

    ax.axhline(y=0.935, xmin=0.03, xmax=0.97, color="#cccccc", lw=0.8,
               transform=ax.transAxes)

    # Metadata block (left column)
    meta = [
        ("script",      manifest.get("script", "?")),
        ("test_type",   test_type),
        ("run_mode",    run_mode),
        ("seed",        f"{seed}  ({sf})"),
        ("n_runs",      str(n_runs)),
        ("N_min",       str(manifest.get("N_min", 50))),
        ("n_runs_ok",   str(manifest.get("n_runs_ok", "?"))),
        ("dataset_id",  dataset_id),
        ("commit_sha",  commit_sha),
    ]
    y = 0.91
    for label, val in meta:
        ax.text(0.05, y, f"{label:<12} : {val}",
                transform=ax.transAxes, va="top",
                fontsize=8.5, family="monospace", color="#333333")
        y -= 0.026

    ax.axhline(y=0.67, xmin=0.03, xmax=0.97, color="#cccccc", lw=0.8,
               transform=ax.transAxes)

    # Decisional fields table
    ax.text(0.05, 0.645, "Decisional fields",
            transform=ax.transAxes, va="top",
            fontsize=10, fontweight="bold", color=C_DARK)

    rows = [(label, _fmt_val(data[key]))
            for key, label in DISPLAY_FIELDS
            if key in data]

    if rows:
        table = ax.table(
            cellText=rows,
            colLabels=["Field", "Value"],
            loc="center",
            cellLoc="left",
            bbox=[0.0, 0.14, 0.65, 0.49],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_facecolor(C_DARK)
                cell.set_text_props(color="white", fontweight="bold")
            else:
                cell.set_facecolor("#f5f5f5" if row % 2 == 0 else "white")
    else:
        ax.text(0.05, 0.55,
                "No statistical fields\n(fixed_data test — deterministic result)",
                transform=ax.transAxes, va="top",
                fontsize=9, color="#666666", style="italic")

    # T2/T3 fixed_data note
    if test_type == "fixed_data":
        ax.text(0.70, 0.55,
                "NOTE\n\nn_runs = 1 is correct\nfor fixed_data tests.\nThe test runs on a\ndeterministic CSV\n(not a simulation).\nThis is NOT smoke_ci.",
                transform=ax.transAxes, va="top", ha="left",
                fontsize=8, color="#555555",
                bbox=dict(boxstyle="round,pad=0.4", fc="#f0f4ff", ec="#aaaacc", lw=1))

    # Rationale / verdict explanation
    rationale = data.get("rationale", "")
    if rationale:
        ax.axhline(y=0.13, xmin=0.03, xmax=0.97, color="#cccccc", lw=0.8,
                   transform=ax.transAxes)
        ax.text(0.05, 0.125, "Rationale:",
                transform=ax.transAxes, va="top",
                fontsize=9, fontweight="bold", color="#444444")
        wrapped = textwrap.fill(str(rationale), width=100)
        ax.text(0.05, 0.095, wrapped,
                transform=ax.transAxes, va="top",
                fontsize=7.5, family="monospace", color="#555555")

    # seed_table.csv inline
    st_path = test_dir / "seed_table.csv"
    if st_path.exists():
        st_text = st_path.read_text(encoding="utf-8").strip()
        ax.text(0.70, 0.33, "seed_table.csv",
                transform=ax.transAxes, va="top",
                fontsize=8, fontweight="bold", color=C_DARK)
        ax.text(0.70, 0.305, st_text,
                transform=ax.transAxes, va="top",
                fontsize=7, family="monospace", color="#333333")

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate isolated T1..T8 proof PDF.")
    ap.add_argument("--run-dir", required=True,
                    help="Directory containing global_summary.json + T*/ subdirs")
    ap.add_argument("--out", default=None,
                    help="Output PDF path (default: <run-dir>/isolated_proof_report.pdf)")
    args = ap.parse_args()

    run_dir  = Path(args.run_dir)
    out_path = Path(args.out) if args.out else run_dir / "isolated_proof_report.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gsum_path = run_dir / "global_summary.json"
    if not gsum_path.exists():
        raise SystemExit(f"global_summary.json not found in {run_dir}")

    gsum      = _load_json(gsum_path)
    run_id    = gsum.get("run_id", run_dir.name)
    timestamp = gsum.get("timestamp_utc", datetime.now(timezone.utc).isoformat())

    with PdfPages(str(out_path)) as pdf:
        _page_cover(pdf, gsum, run_id, timestamp)

        for short, test_id in ORDERED_TESTS:
            test_dir = run_dir / test_id
            _page_test(pdf, short, test_id, test_dir)

        d = pdf.infodict()
        d["Title"]   = f"ORI-C Isolated T1..T8 Proof — {run_id}"
        d["Author"]  = "ORI-C Pipeline"
        d["Subject"] = (
            f"Isolated test proof | run_mode={gsum.get('run_mode')} | "
            f"{gsum.get('n_accept', 0)}/8 ACCEPT | "
            f"seeds_distinct={gsum.get('seeds_distinct')}"
        )

    print(f"PDF written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
