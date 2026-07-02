# Example filled: Test 6 (S*) symbolic threshold
Date: 2026-02-17
Status: example only (not evidence)

## Goal
Demonstrate a clean non-linear transition where an increase in S produces:
- C approximately zero below a threshold S*
- C positive and stable above S*
- optional later cut to test Test 7 with ORI held constant

## Input dataset
`03_Data/synthetic/synthetic_test6_s_star.csv`

This dataset includes:
- ORI constants: O, R, I fixed.
- Demand ramp: demande_env increases over time to create Sigma.
- S components increase stepwise to induce a symbolic transition.
- Flags:
  - perturb_symbolic for optional stress on S
  - cut_symbolic for an optional cut event

## How to run
1) Build processed time series and per-run summaries:

```bash
python 04_Code/pipeline/run_canonical_suite.py --input 03_Data/synthetic/synthetic_test6_s_star.csv --outdir 05_Results/demo_test6 --n-runs 50 --master-seed 42
```

2) Produce local and global verdicts using the decision protocol:

```bash
python 04_Code/pipeline/analyse_verdicts_canonical.py --runs 05_Results/demo_test6/tables/runs_summary.csv --outdir 05_Results/demo_test6/derived
```

## Expected pattern
- `detect_s_star_piecewise` returns a non-trivial improvement value.
- Local Test 6 is expected to be ACCEPT only if the effect meets SESOI and passes quality and power gates.

## Notes
This example is meant to validate the pipeline and the reporting structure.
It is not a claim about real data.
