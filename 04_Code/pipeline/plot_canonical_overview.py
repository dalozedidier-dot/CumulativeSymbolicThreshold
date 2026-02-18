#!/usr/bin/env python3
# 04_Code/pipeline/plot_canonical_overview.py
"""
Utility: compile an overview figure from canonical test outputs.

Usage:
python 04_Code/pipeline/plot_canonical_overview.py --run-dir 05_Results/canonical_tests/<timestamp>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    figdir = run_dir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    panels = []

    # T4, T5, T7 summaries if present
    for tid in [
        "T4_symbolic_S_rich_vs_poor_on_C",
        "T5_symbolic_injection_effect_on_C",
        "T7_progressive_S_to_C_threshold",
    ]:
        found = None
        for sub in run_dir.iterdir():
            if sub.is_dir() and tid.split("_")[0] in sub.name:
                sj = sub / "tables" / "summary.json"
                if sj.exists():
                    found = _read_json(sj)
                    break
        panels.append((tid, found))

    # Build a simple one-page summary as text blocks
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)
    ax.axis("off")

    lines = ["Canonical overview (symbolic tests)"]
    lines.append("")
    for tid, s in panels:
        lines.append(tid)
        if not s:
            lines.append("  missing")
            lines.append("")
            continue
        for k in ["verdict", "delta_C_end", "effect_sd", "p_value_welch", "delta_bic_linear_minus_piecewise"]:
            if k in s:
                lines.append(f"  {k}: {s[k]}")
        lines.append("")

    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", family="monospace")
    fig.tight_layout()
    fig.savefig(figdir / "canonical_symbolic_overview.png", dpi=200)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
