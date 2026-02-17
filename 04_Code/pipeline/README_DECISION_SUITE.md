# Canonical decision suite

This folder contains two scripts that implement a minimal, audit-friendly pipeline.

1) `run_canonical_suite.py`
- builds processed time series
- writes `tables/runs_summary.csv`

2) `analyse_verdicts_canonical.py`
- applies the decision protocol gates and produces verdict files

These scripts are designed to coexist with existing scripts in the repository.
They do not remove or replace any previous pipeline.
