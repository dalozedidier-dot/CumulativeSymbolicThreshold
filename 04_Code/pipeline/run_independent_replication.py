#!/usr/bin/env python3
"""run_independent_replication.py — Independent replication of the ORI-C validation.

This script verifies that the validation protocol verdict is reproducible:
  1. With completely different seeds (no overlap with calibration seeds)
  2. Without any parameter retuning (loads frozen params, never modifies them)
  3. Produces consistent verdicts across replication batches

Usage:
  python 04_Code/pipeline/run_independent_replication.py \
    --outdir 05_Results/replication --n-batches 3 --n-per-batch 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from oric.frozen_params import FROZEN_PARAMS, FrozenValidationParams
from pipeline.run_scientific_validation_protocol import run_validation_protocol


def main() -> int:
    ap = argparse.ArgumentParser(description="Independent replication of ORI-C validation")
    ap.add_argument("--outdir", default="05_Results/replication")
    ap.add_argument("--n-batches", type=int, default=3, help="Number of independent replication batches")
    ap.add_argument("--n-per-batch", type=int, default=30, help="Replicates per condition per batch")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Use completely different seed ranges for each batch
    # Offset by 100000+ to avoid any overlap with calibration seeds (7000-7149)
    batch_seeds = [100000 + i * 50000 for i in range(args.n_batches)]

    batch_results = []

    for batch_idx, seed_offset in enumerate(batch_seeds):
        batch_dir = outdir / f"batch_{batch_idx + 1:02d}"

        # Create a new FrozenValidationParams with different seed_base
        # but IDENTICAL thresholds (no retuning)
        fp_batch = FrozenValidationParams(
            seed_base=seed_offset,
            n_replicates=args.n_per_batch,
            # All other params identical to FROZEN_PARAMS
            alpha=FROZEN_PARAMS.alpha,
            sesoi_c_robust_sd=FROZEN_PARAMS.sesoi_c_robust_sd,
            ci_level=FROZEN_PARAMS.ci_level,
            contrast_margin=FROZEN_PARAMS.contrast_margin,
            contrast_Q_test=FROZEN_PARAMS.contrast_Q_test,
            test_detection_rate_min=FROZEN_PARAMS.test_detection_rate_min,
            stable_fp_rate_max=FROZEN_PARAMS.stable_fp_rate_max,
            placebo_fp_rate_max=FROZEN_PARAMS.placebo_fp_rate_max,
            min_decidable_per_condition=FROZEN_PARAMS.min_decidable_per_condition,
            max_indeterminate_rate=FROZEN_PARAMS.max_indeterminate_rate,
            n_steps=FROZEN_PARAMS.n_steps,
            intervention_point=FROZEN_PARAMS.intervention_point,
            intervention_duration=FROZEN_PARAMS.intervention_duration,
            k=FROZEN_PARAMS.k,
            m=FROZEN_PARAMS.m,
            baseline_n=FROZEN_PARAMS.baseline_n,
            sigma_star=FROZEN_PARAMS.sigma_star,
            tau=FROZEN_PARAMS.tau,
            demand_noise=FROZEN_PARAMS.demand_noise,
            ori_trend=FROZEN_PARAMS.ori_trend,
            power_bootstrap_B=FROZEN_PARAMS.power_bootstrap_B,
            power_gate_min=FROZEN_PARAMS.power_gate_min,
        )

        if not args.quiet:
            print(f"\n{'#'*60}")
            print(f"  REPLICATION BATCH {batch_idx + 1}/{args.n_batches}")
            print(f"  Seed base: {seed_offset}")
            print(f"{'#'*60}")

        result = run_validation_protocol(
            outdir=batch_dir,
            fp=fp_batch,
            n_replicates=args.n_per_batch,
            verbose=not args.quiet,
        )

        batch_results.append({
            "batch": batch_idx + 1,
            "seed_base": seed_offset,
            "n_per_batch": args.n_per_batch,
            "verdict": result["protocol_verdict"],
            "sensitivity": result["discrimination_metrics"]["sensitivity"],
            "specificity": result["discrimination_metrics"]["specificity"],
            "fisher_p": result["discrimination_metrics"]["fisher_p_value"],
            "n_decidable": result["discrimination_metrics"]["n_decidable"],
        })

    # Aggregate replication results
    verdicts = [b["verdict"] for b in batch_results]
    all_accept = all(v == "ACCEPT" for v in verdicts)
    any_reject = any(v == "REJECT" for v in verdicts)

    if all_accept:
        replication_verdict = "REPLICATED"
    elif any_reject:
        replication_verdict = "REPLICATION_FAILED"
    else:
        replication_verdict = "REPLICATION_PARTIAL"

    sensitivities = [b["sensitivity"] for b in batch_results]
    specificities = [b["specificity"] for b in batch_results]

    replication_summary = {
        "replication_verdict": replication_verdict,
        "n_batches": args.n_batches,
        "n_per_batch": args.n_per_batch,
        "batch_results": batch_results,
        "verdicts": verdicts,
        "mean_sensitivity": float(np.mean(sensitivities)),
        "std_sensitivity": float(np.std(sensitivities)),
        "mean_specificity": float(np.mean(specificities)),
        "std_specificity": float(np.std(specificities)),
        "consistency": "all batches agree" if len(set(verdicts)) == 1 else "batches disagree",
        "parameters_retuned": False,
        "note": "All batches used identical frozen parameters with non-overlapping seeds.",
    }

    (outdir / "replication_summary.json").write_text(
        json.dumps(replication_summary, indent=2, default=str), encoding="utf-8"
    )
    (outdir / "replication_verdict.txt").write_text(
        replication_verdict + "\n", encoding="utf-8"
    )

    print(f"\n{'='*60}")
    print(f"  REPLICATION VERDICT: {replication_verdict}")
    print(f"{'='*60}")
    for b in batch_results:
        print(f"  Batch {b['batch']}: {b['verdict']}  "
              f"sens={b['sensitivity']:.3f}  spec={b['specificity']:.3f}")
    print(f"  Mean sensitivity: {np.mean(sensitivities):.4f} +/- {np.std(sensitivities):.4f}")
    print(f"  Mean specificity: {np.mean(specificities):.4f} +/- {np.std(specificities):.4f}")
    print(f"{'='*60}\n")

    return 0 if replication_verdict == "REPLICATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
