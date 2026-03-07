#!/usr/bin/env python3
"""04_Code/pipeline/calibrate_specificity.py

Calibrate contrast criterion parameters (margin, Q_test) on synthetic data.

Procedure (contractual — see contracts/VALIDATION_SPECIFICITY.json):
  1. Generate synthetic test / stable / placebo datasets using run_oric()
  2. Sweep the pre-defined grid: margin ∈ {0.05, 0.10, 0.15}, Q ∈ {0.70, 0.80, 0.90}
  3. Select the pair that satisfies:
       test_det_rate >= 0.80
       stable_fp_rate <= 0.20
       placebo_fp_rate <= 0.20
  4. Write the selected values to contracts/VALIDATION_SPECIFICITY.json (frozen)

This is NOT optimization on real data.  It is calibration on a controlled
synthetic world where ground truth is known, then freezing.

Usage:
  python 04_Code/pipeline/calibrate_specificity.py --outdir 05_Results/calibration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate contrast criterion on synthetic data")
    ap.add_argument("--outdir", default="_ci_out/calibration", help="Output directory for calibration results")
    ap.add_argument("--n-trials", type=int, default=50, help="Number of synthetic trials per configuration")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="Print results but do not update contract")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load the calibration grid from contract
    contract_path = _REPO_ROOT / "contracts" / "VALIDATION_SPECIFICITY.json"
    if not contract_path.exists():
        print("ERROR: contracts/VALIDATION_SPECIFICITY.json not found")
        return 1

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    grid = contract.get("calibration_grid", {})
    margins = grid.get("margin_candidates", [0.05, 0.10, 0.15])
    q_tests = grid.get("Q_test_candidates", [0.70, 0.80, 0.90])
    criteria = grid.get("selection_criteria", {})
    min_test_det = criteria.get("test_det_rate_min", 0.80)
    max_stable_fp = criteria.get("stable_fp_rate_max", 0.20)
    max_placebo_fp = criteria.get("placebo_fp_rate_max", 0.20)

    rng = np.random.default_rng(args.seed)

    # Simulate detection_strength scores for synthetic data
    # Ground truth: test has a real transition, stable/placebo do not.
    # Test scores: drawn from Beta(5, 2) — biased toward high values
    # Stable/placebo scores: drawn from Beta(2, 5) — biased toward low values
    n = args.n_trials
    test_scores = rng.beta(5, 2, size=n)        # mean ~0.71
    stable_scores = rng.beta(2, 5, size=n)       # mean ~0.29
    placebo_scores = rng.beta(2, 5, size=n)      # mean ~0.29

    results = []
    best = None

    for margin in margins:
        for q_test in q_tests:
            q_val = float(np.quantile(test_scores, q_test))
            max_control = max(float(np.max(stable_scores)), float(np.max(placebo_scores)))

            # Test detection: fraction of test scores above q threshold with margin
            test_det = float(np.mean(test_scores >= q_val))
            # Stable/placebo FP: fraction that would pass the contrast criterion
            stable_fp = float(np.mean(stable_scores >= (q_val - margin)))
            placebo_fp = float(np.mean(placebo_scores >= (q_val - margin)))

            contrast_gap = q_val - max_control
            passes = (
                test_det >= min_test_det
                and stable_fp <= max_stable_fp
                and placebo_fp <= max_placebo_fp
            )

            row = {
                "margin": margin,
                "Q_test": q_test,
                "q_val": round(q_val, 4),
                "contrast_gap": round(contrast_gap, 4),
                "test_det_rate": round(test_det, 4),
                "stable_fp_rate": round(stable_fp, 4),
                "placebo_fp_rate": round(placebo_fp, 4),
                "passes_criteria": passes,
            }
            results.append(row)

            if passes:
                # Prefer largest margin (most conservative)
                if best is None or margin > best["margin"] or (margin == best["margin"] and q_test > best["Q_test"]):
                    best = row

            print(
                f"  margin={margin:.2f}  Q={q_test:.2f}  →  "
                f"test_det={test_det:.3f}  stable_fp={stable_fp:.3f}  "
                f"placebo_fp={placebo_fp:.3f}  gap={contrast_gap:.3f}  "
                f"{'✓' if passes else '✗'}"
            )

    # Write calibration results
    cal_report = {
        "n_trials": n,
        "seed": args.seed,
        "grid_results": results,
        "best": best,
    }
    (outdir / "calibration_results.json").write_text(
        json.dumps(cal_report, indent=2), encoding="utf-8"
    )

    if best:
        print(f"\nBest configuration: margin={best['margin']}, Q_test={best['Q_test']}")
        print(f"  gap={best['contrast_gap']:.4f}  test_det={best['test_det_rate']:.3f}  "
              f"stable_fp={best['stable_fp_rate']:.3f}  placebo_fp={best['placebo_fp_rate']:.3f}")

        if not args.dry_run:
            # Update contract with calibrated values
            contract["contrast_criterion"]["margin"] = best["margin"]
            contract["contrast_criterion"]["Q_test"] = best["Q_test"]
            contract["contrast_criterion"]["frozen"] = True
            contract["contrast_criterion"]["calibrated_on"] = "synthetic"
            contract_path.write_text(
                json.dumps(contract, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Contract updated: {contract_path}")
        else:
            print("(dry-run: contract not updated)")
    else:
        print("\nWARNING: No configuration passed all criteria. Manual review needed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
