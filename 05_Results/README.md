# 05_Results — current generated outputs

This directory is reserved for current, regenerated outputs only.

The previous committed results were stale and have been moved to `99_Archive/stale_05_Results_20260702/`. In particular, the old FRED monthly PDF reported `GLOBAL VERDICT: ACCEPT` from 2026-02-21 and no longer represents the current validation state.

Regenerate current results with the smoke CI workflow or locally with:

```bash
PYTHONPATH=src python 04_Code/pipeline/run_all_tests.py --outdir 05_Results/canonical_tests --fast
```

Use the nightly proof workflow for full statistical runs.
