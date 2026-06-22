#!/usr/bin/env python3
"""run_registered_block.py — execute the frozen, pre-registered real-data A/B/C block.

Loads ``contracts/REAL_DATA_REGISTRATION.json`` (everything frozen ex ante: dataset,
dated hypothesis window, proxy/normalisation, k/m/baseline_n, ACCEPT/REJECT criteria,
classical benchmark panel, surrogate config, OOS split, aggregation rule), runs the
ORI-C localized detector + classical baselines (CUSUM, dependency-free PELT, EWS,
structural break) on A / B(stable) / C(placebo), an IAAFT surrogate null on A and a
pre-t* out-of-sample split, then aggregates into ONE verdict token.

Outputs
  tables/registered_block.json   full structured result + verdict
  tables/registered_block.csv    flat per-condition / per-method table
  figures/registered_block.png   C(t), ΔC vs threshold, hypothesis window, controls
  verdict.txt                    REAL_BLOCK_CONFIRMED / _REJECTED / _INDETERMINATE
  manifest.json                  audit trail (contract sha, seeds, params, json sha)

This is a diagnostic, registered artefact (exit 0 even on REJECTED — an honest
negative). Designed to finish in ~minutes; see docs/EVIDENCE_LADDER.md (rungs 5-6).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_HERE))

from oric.registered_block import run_registered_block  # noqa: E402

_CONTRACT = _REPO / "contracts" / "REAL_DATA_REGISTRATION.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _plot(result: dict, A_C, A_dc, contract: dict, figpath: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as exc:  # pragma: no cover
        print(f"  [figure] skipped: {exc}")
        return
    t1 = result["dated_hypothesis"]["t1"]
    t2 = result["dated_hypothesis"]["t2"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axes[0].plot(A_C, color="#1f77b4", lw=1.1)
    axes[0].axvspan(t1, t2, color="#ffcc99", alpha=0.5, label="hypothesis window")
    axes[0].set_ylabel("C(t)")
    axes[0].set_title(f"Registered block — {result['dataset_A']} — VERDICT={result['verdict']}", fontsize=10)
    axes[0].legend(fontsize=8)
    axes[1].plot(A_dc, color="#2ca02c", lw=0.9)
    mu = float(np.mean(A_dc[:50]))
    sd = float(np.std(A_dc[:50]))
    axes[1].axhline(mu + 2.5 * sd, ls="--", color="#d62728", lw=1.0, label="ΔC threshold (μ+kσ)")
    axes[1].axvspan(t1, t2, color="#ffcc99", alpha=0.5)
    axes[1].set_ylabel("ΔC")
    axes[1].set_xlabel("t (months)")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figpath, dpi=110)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the frozen registered real-data A/B/C block")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--contract", default=str(_CONTRACT))
    ap.add_argument("--fast", action="store_true", help="fewer surrogates (~minutes)")
    args = ap.parse_args()

    contract_path = Path(args.contract)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    A_path = _REPO / contract["dataset_A"]["path"]
    datasets = {"A": pd.read_csv(A_path)}
    ext = contract.get("external_stable")
    if ext and (_REPO / ext["path"]).exists():
        datasets["external_stable"] = pd.read_csv(_REPO / ext["path"])

    print(f"[REGISTERED-BLOCK] A={contract['dataset_A']['id']} "
          f"hypothesis={contract['dated_hypothesis']['label']} fast={args.fast}")
    result = run_registered_block(contract, datasets, fast=args.fast)

    out = Path(args.outdir)
    tables = out / "tables"
    figures = out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    json_path = tables / "registered_block.json"
    json_path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    (out / "verdict.txt").write_text(result["verdict"] + "\n", encoding="utf-8")

    # Flat CSV: one row per (condition, method).
    import csv as _csv
    with open(tables / "registered_block.csv", "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["condition", "method", "detected", "detection_point", "statistic", "p_value"])
        w.writerow(["A", "oric_localized", result["A"]["detected"], result["A"]["detection_point"], result["A"]["crossing_rate"], result["surrogate"]["p_value"]])
        for cond, panel in result["classical"].items():
            for method, r in panel.items():
                w.writerow([cond, method, r.get("detected"), r.get("detection_point"), r.get("statistic"), r.get("p_value")])

    # Figure (recompute A's C/ΔC deterministically for plotting).
    try:
        from oric.registered_block import oric_localized_detect
        cr = result["criteria"]
        a = oric_localized_detect(datasets["A"], k=cr["k"], m=cr["m"], baseline_n=cr["baseline_n"], seed=cr["seed"])
        _plot(result, a["C"], a["delta_C"], contract, figures / "registered_block.png")
    except Exception as exc:  # pragma: no cover
        print(f"  [figure] skipped: {exc}")

    manifest = {
        "test_id": "registered_block",
        "schema": "oric.registered_block.manifest.v1",
        "contract_sha256": _sha256(contract_path) if contract_path.exists() else None,
        "dataset_A": result["dataset_A"],
        "dated_hypothesis": result["dated_hypothesis"],
        "criteria": result["criteria"],
        "verdict": result["verdict"],
        "reasons": result["reasons"],
        "json_sha256": _sha256(json_path),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"\n{'='*66}")
    print(f"  A detected (in-window) : {result['A']['detected']} ({result['A']['in_window']})")
    print(f"  B silent / C silent    : {result['B_silent']} / {result['C_silent']}")
    print(f"  IAAFT surrogate p      : {result['surrogate']['p_value']:.3f} (sig@0.01={result['surrogate']['significant_at_01']})")
    print(f"  classical FP on B+C    : {result['classical_false_positives_on_controls']}")
    print(f"  OOS directional skill  : {result['oos'].get('directional_skill')}")
    print(f"  VERDICT                : {result['verdict']}")
    for r in result["reasons"]:
        print(f"    - {r}")
    print(f"{'='*66}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
