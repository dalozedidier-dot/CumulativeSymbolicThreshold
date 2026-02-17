# Neuro extension (optional) for ORI-C

Version: v1.0
Date: 2026-02-17
Status: Optional, non-decision-critical unless preregistered as such.

This repo can host lightweight neuroscience-computation demos that map ORI-C variables to:
- micro-scale plasticity (BCM-like rule),
- meso-scale attractor stability (bump attractor persistence).

The goal is not to claim biological truth. The goal is to provide a testbed where:
- a capacity proxy (Cap) exists,
- overload or mismatch (Sigma) can be imposed,
- viability proxy (V) degrades under sustained mismatch,
- a "symbolic-like" stock (S) can be operationalized as a slow state variable.

## Test 9A: Bump attractor stability (meso-scale)
Script:
- 04_Code/pipeline/run_bump_attractor.py

Outputs:
- tables/bump_runs.csv: per-run metrics.
- tables/summary.csv: aggregated metrics and local verdict.
- figures/: diagnostics and example traces.

Interpretation mapping (minimal):
- Cap proxy: attractor stability range as a function of recurrent gain.
- Sigma proxy: drift or loss of bump under overload or noise.
- V proxy: persistence score (higher is better).

## Test 9B: BCM plasticity with cut and reinjection (micro-scale)
Scripts:
- 04_Code/pipeline/bcm_plasticity.py (core simulator)
- 04_Code/pipeline/run_bcm_test.py (CLI runner)

Outputs:
- tables/bcm_timeseries.csv: time series.
- tables/summary.csv: metrics for cut and reinjection and local verdict.
- figures/: time series plots.

Interpretation mapping (minimal):
- S proxy: slow threshold variable (theta_M) and or running activity trace (c_bar).
- C proxy: weight (w) or performance proxy that shows cumulative change.
- U(t): cut or reinjection schedule on input drive.
