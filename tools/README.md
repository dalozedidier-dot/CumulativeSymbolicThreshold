# tools/ — CLI utilities and CI tooling

Scripts for CI automation, quality control checks, and data management.

## Core tools

| Script | Purpose |
|--------|---------|
| `collect_ci_metrics.py` | Collect and store CI run metrics |
| `repair_ci_metrics.py` | Repair/normalize CI metrics history |
| `enforce_output_contract.py` | Validate pipeline outputs against contracts |
| `repo_doctor.py` | Repository health checks |
| `make_manifest.py` | Generate SHA-256 manifest for run outputs |
| `stage_contracts.py` | Stage validation contracts |
| `verify_audit_invariants.py` | Verify audit trail invariants |

## Collector tools

| Script | Purpose |
|--------|---------|
| `collector_download_artifacts.py` | Download CI artifacts |
| `collector_download_artifacts_runlist.py` | Batch download from run list |

## QCC (Quantum Contextual Computing) tools

| Script | Purpose |
|--------|---------|
| `qcc_checks.py` | QCC validation checks |
| `qcc_stateprob_*.py` | State-probability variant tools |
| `qcc/` | QCC subpackage |

## Workflow management

| Script | Purpose |
|--------|---------|
| `disable_noisy_workflows.py` | Disable noisy/deprecated workflows |
| `disable_workflows.py` | Bulk workflow management |
| `run_scan_only.py` | Run scan-only mode |
