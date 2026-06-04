# Check-up ORI-C repository

Date: 2026-06-04

## Scope

Archive inspected: `CumulativeSymbolicThreshold-main (7).zip`.

The check-up focused on repository health, Python syntax, workflow validity, CI action compatibility, smoke execution, and obvious generated-cache cleanup.

## Findings

### OK

- Python syntax compilation passes for:
  - `src/`
  - `04_Code/`
  - `scripts/`
  - `tools/`
- GitHub workflow YAML files parse correctly.
- `tools/repo_doctor.py` reports `PASS`.
- A targeted pytest subset covering package smoke tests, tools tests, artifact consistency, final gate proof dimensions, nightly/sector verdict alignment and ORI-C pipeline tests passes.
- Synthetic demo smoke run succeeds on `03_Data/synthetic/synthetic_minimal.csv` and produces expected outputs:
  - `figures/c_t_with_threshold.png`
  - `figures/v_t_perturbation.png`
  - `tables/processed_synthetic.csv`
  - `tables/summary.json`
  - `tables/verdict.json`
  - `verdict.txt`

### Corrected

- Replaced unsupported or non-standard GitHub Action versions in active workflows:
  - `actions/checkout@v6` -> `actions/checkout@v4`
  - `actions/upload-artifact@v7` -> `actions/upload-artifact@v4`
  - `actions/download-artifact@v8` -> `actions/download-artifact@v4`
- Cleaned local generated cache directories from the archive:
  - `__pycache__/`
  - `.pytest_cache/`

## Files modified

- `.github/workflows/ci.yml`
- `.github/workflows/collector.yml`
- `.github/workflows/nightly.yml`
- `.github/workflows/qcc_canonical_full.yml`
- `.github/workflows/sector_pilots.yml`
- `CHECKUP_REPORT_2026-06-04.md` added

## Validation commands run

```bash
python -m compileall src 04_Code scripts tools -q
python tools/repo_doctor.py
pytest -q src/oric/tests tools/tests \
  04_Code/tests/test_artifact_consistency_audit.py \
  04_Code/tests/test_dual_proof_manifest_fallback.py \
  04_Code/tests/test_final_gate_proof_dimensions.py \
  04_Code/tests/test_nightly_sector_verdict_alignment.py \
  04_Code/tests/test_oric_pipeline.py \
  04_Code/tests/test_sector_summary_verdict_alignment.py --tb=short
PYTHONPATH=src python 04_Code/pipeline/run_synthetic_demo.py \
  --input 03_Data/synthetic/synthetic_minimal.csv \
  --outdir /tmp/oric_smoke \
  --seed 1
```

## Limits

- The full pytest suite was not completed in this environment because the full suite is long-running. It started successfully and many tests passed before timeout.
- No scientific thresholds, model logic, contracts, or datasets were altered.
- The correction is intentionally conservative: CI reliability and repository hygiene only.
