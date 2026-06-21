#!/usr/bin/env python3
"""run_multiverse.py — Specification-curve / multiverse robustness for a dataset.

Runs ORI-C across a pre-declared grid of equally-defensible analytic
specifications (normalisation × smoothing × auto-scale target) and reports the
full distribution of verdicts. A genuine signature survives most defensible
choices; an ACCEPT that holds for only one is fragile.

Usage
  python 04_Code/pipeline/run_multiverse.py \
    --input 03_Data/real/fred_monthly/real.csv \
    --outdir 05_Results/multiverse/fred --seed 1234

Outputs
  tables/multiverse.json        per-spec outcomes + robustness verdict
  tables/multiverse.csv         flat table
  figures/specification_curve.png  sorted crossing-rate spec curve (fired highlighted)
  verdict.txt                   ROBUST_POSITIVE / ROBUST_NEGATIVE / FRAGILE
  manifest.json                 audit trail
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_HERE))

from oric.multiverse import run_multiverse, specification_grid  # noqa: E402
from ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    missing = [c for c in ("O", "R", "I") if c not in df.columns]
    if missing:
        raise SystemExit(f"input {input_csv} missing required columns: {missing}")
    if "t" not in df.columns:
        df.insert(0, "t", np.arange(len(df)))
    return df


def _plot(result: dict, figpath: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"  [figure] skipped: {exc}")
        return
    outs = sorted(result["outcomes"], key=lambda o: o["crossing_rate"])
    rates = [o["crossing_rate"] for o in outs]
    colours = ["#2ca02c" if o["detector_fired"] else "#bbbbbb" for o in outs]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(range(len(rates)), rates, color=colours)
    ax.set_xlabel(f"specification (sorted) — {result['n_specs']} defensible analytic choices")
    ax.set_ylabel("threshold crossing rate")
    ax.set_title(f"ORI-C specification curve — {result['robustness']} "
                 f"(fired in {result['fired_fraction']*100:.0f}% of specs)")
    fig.tight_layout()
    fig.savefig(figpath, dpi=110)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C specification-curve / multiverse")
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=30)
    args = ap.parse_args()

    out = Path(args.outdir)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    df = _load(Path(args.input))
    cfg = ORICConfig(seed=args.seed, n_steps=len(df), intervention="none",
                     k=args.k, m=args.m, baseline_n=args.baseline_n)

    specs = specification_grid()
    print(f"[MULTIVERSE] input={args.input} rows={len(df)} specs={len(specs)}")
    result = run_multiverse(df, cfg, specs=specs, run_fn=run_oric_from_observations)
    result["input"] = str(args.input)
    result["n_rows"] = int(len(df))

    with open(out / "tables" / "multiverse.json", "w") as f:
        json.dump(result, f, indent=2)

    with open(out / "tables" / "multiverse.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["normalize", "smooth", "demand_to_cap_ratio", "detector_fired", "crossing_rate", "max_run"])
        for o in result["outcomes"]:
            s = o["spec"]
            w.writerow([s["normalize"], s["smooth"], s["demand_to_cap_ratio"],
                        o["detector_fired"], o["crossing_rate"], o["max_run"]])

    _plot(result, out / "figures" / "specification_curve.png")
    (out / "verdict.txt").write_text(result["robustness"])

    manifest = {
        "test_id": "multiverse",
        "schema": "oric.multiverse.manifest.v1",
        "input": str(args.input),
        "seed": args.seed,
        "n_specs": result["n_specs"],
        "fired_fraction": result["fired_fraction"],
        "robustness": result["robustness"],
        "json_sha256": _sha256(out / "tables" / "multiverse.json"),
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    q = result["crossing_rate_quartiles"]
    print(f"\n  specs fired: {result['fired_fraction']*100:.0f}%  "
          f"crossing-rate median={q['median']:.3f} [{q['min']:.3f}, {q['max']:.3f}]")
    print(f"  ROBUSTNESS: {result['robustness']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
