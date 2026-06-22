# Correction notes

## What was corrected

The main correction is the trend-vs-transition detector.

The old gate only checked whether `delta_C` stayed above a baseline threshold for `m` consecutive steps. That was too permissive because a smooth accumulation could produce a long sustained crossing without a real localized regime change.

The current code now records two gates:

- `raw_detector_fired`: the old sustained `delta_C` crossing, kept for audit continuity.
- `detector_fired`: the conservative localized-transition gate, which also requires the positive acceleration of smoothed `delta_C` to be concentrated in a short temporal window.

## Immediate control result

On the shipped accumulation-control catalogue:

- `raw_accumulation_fpr = 1.0`
- `accumulation_fpr = 0.0`
- `bifurcation_tpr = 1.0`
- `separates = true`

This means the old detector still exposes the trend confound, but the current localized gate separates smooth accumulations from the shipped synthetic bifurcations.

## What remains not confirmed

This correction does not make the real-data pilots confirmed.

A fast confirmatory rerun gives:

- Pantheon SN: Test A passes, multiverse and effect-size pass, but the surrogate-null gate still fails. Joint verdict: `NOT_CONFIRMED`.
- FRED monthly: Test A passes, but surrogate-null and multiverse fail. Joint verdict: `NOT_CONFIRMED`.

So the corrected status is: detector specificity patched, real-data confirmation still pending.

## Practical fix

`run_all_tests.py` no longer crashes when `--outdir` is an absolute path outside the repository. Manifest paths now serialize as relative paths when possible and absolute paths otherwise.

## Files changed

- `src/oric/surrogates.py`
- `src/oric/accumulation_controls.py`
- `04_Code/pipeline/run_accumulation_control.py`
- `04_Code/pipeline/run_all_tests.py`
- `04_Code/tests/test_accumulation_controls.py`
- `04_Code/tests/test_run_all_tests_paths.py`
- `README.md`
- `docs/EVIDENTIARY_STATUS.md`
- `docs/INDEX.md`
- `docs/framework_status.md`
- `05_Results/PILOT_GENERALIZATION_REPORT.md`

## Checks run

```bash
python -m compileall src 04_Code scripts tools -q
PYTHONPATH=src:04_Code:04_Code/pipeline pytest -q \
  04_Code/tests/test_accumulation_controls.py \
  04_Code/tests/test_confirmatory.py \
  04_Code/tests/test_surrogates.py \
  04_Code/tests/test_run_all_tests_paths.py
```

Result: 22 tests passed for the targeted suite.

Ruff was not available in the execution environment, so I could not run `ruff check` here.
