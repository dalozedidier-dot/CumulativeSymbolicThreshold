# ORI-C Canonical Closure Pack

**Version**: 1.0
**Date**: 2026-03-08
**Schema**: `oric.closure_pack.v1`

---

## 1. What ORI-C Claims

ORI-C (Order–Rigidity–Inertia–Criticality) is a theoretical framework
proposing that cumulative symbolic thresholds govern regime transitions
in complex adaptive systems.  Specifically:

- **Claim**: When the symbolic order variable C(t) crosses a critical
  threshold s*, the system undergoes a detectable phase transition
  characterised by changes in stock S(t), rigidity R(t), and demand patterns.

- **Scope**: The framework is formalised mathematically and tested on
  both synthetic (controlled) and real (economic, FRED) data.

---

## 2. What ORI-C Demonstrates

### 2.1 Dual Proof Architecture

The framework uses a **dual proof** structure:

| Dimension | Source | Status |
|-----------|--------|--------|
| Synthetic | Scientific validation protocol (50 replicates × 3 conditions) | Gate-controlled |
| Real data (FRED) | Canonical real-data validation on FRED monthly series | Validated |
| Validation protocol | Confusion matrix with sensitivity/specificity/Fisher test | Protocol-controlled |

**Contract reference**: `contracts/DUAL_PROOF_CONTRACT.json`

### 2.2 Scientific Validation Protocol

The validation protocol proves **discrimination** through three conditions:

- **TEST**: Demand shock intervention at t=900 → expected DETECTED
- **STABLE**: No intervention, identical trajectories → expected NOT_DETECTED
- **PLACEBO**: Multi-surrogate battery (5 strategies) → expected NOT_DETECTED

**Key metrics** (from frozen benchmark):
- Sensitivity (TPR) ≥ 0.80
- Specificity (TNR) ≥ 0.80
- Fisher exact test p < 0.01
- Indeterminate rate < 0.40 per condition

**Contract references**:
- `contracts/FROZEN_PARAMS.json`
- `contracts/VALIDATION_SPECIFICITY.json`
- `contracts/VALIDATION_DECIDABILITY.json`

### 2.3 Evidence Levels

| Level | Label | Requirements | Datasets |
|-------|-------|-------------|----------|
| **A** | Canonical demonstration | n≥200, prechecks pass, causal tests, decidable verdict | `fred_monthly`, `synthetic` |
| **B** | Exploratory multi-sector | Pipeline runs, proxy loads, C(t) responds | Sector pilots |

Level B is NOT canonical proof.  It demonstrates feasibility and compatibility,
not statistical proof.

**Contract reference**: `contracts/VALIDATION_BENCHMARK.json → evidence_levels`

---

## 3. What ORI-C Does NOT Demonstrate (Yet)

### 3.1 Known Limitations

1. **Placebo specificity**: The original single-strategy cyclic-shift placebo
   was detected at ~100%.  The multi-surrogate battery (ticket 6) provides
   structurally diverse null hypotheses but full validation is ongoing.

2. **Stable decidability**: Stable runs produce high indeterminate rates due
   to near-zero C variance.  Adapted prechecks (relaxed `min_unique_values_C=3`,
   `min_variance_C=1e-15`) improve decidability but do not eliminate it.

3. **Real-data generality**: Only FRED monthly is canonical (Level A).
   All sector pilots (climate, finance, AI-tech, psych, social) are Level B —
   exploratory demonstrations, not proof.

4. **Independent replication**: Bloc 4 (external proof) is PENDING.
   No independent team has replicated the results with frozen protocol.

5. **Causal identification**: The framework detects regime transitions but
   does not establish causality.  The O→R→I→demand→S chain is a theoretical
   model, not a proven causal mechanism.

### 3.2 Open Questions

- Can the framework achieve `protocol_verdict = ACCEPT` on the full 50-replicate
  benchmark with the multi-surrogate placebo battery?
- What is the achievable stable decidable_fraction with adapted prechecks
  on real data (not just synthetic)?
- Does the framework generalise to non-economic domains at Level A?

---

## 4. How to Reproduce the Results

### 4.1 Prerequisites

```
Python >= 3.11
numpy, pandas, scipy, pytest
```

### 4.2 Run the Validation Protocol

```bash
python 04_Code/pipeline/run_scientific_validation_protocol.py \
  --outdir 05_Results/scientific_validation \
  --n-replicates 50
```

### 4.3 Run the Reference Benchmark Test

```bash
python -m pytest 04_Code/tests/test_validation_protocol_reference_benchmark.py -v
```

### 4.4 Run the Full Test Suite

```bash
python -m pytest 04_Code/tests/ -v
```

### 4.5 Run the Artifact Consistency Audit

```bash
python tools/audit_artifact_consistency.py --bundle-dir <results_dir>
```

### 4.6 Build the Proof Package

```python
from oric.proof_manifest import build_dual_proof_manifest, build_final_status
from oric.proof_package import build_proof_package

manifest = build_dual_proof_manifest(
    synthetic_dir=Path("05_Results/scientific_validation"),
    fred_dir=Path("05_Results/fred_validation"),
    validation_dir=Path("05_Results/scientific_validation"),
)
final_status = build_final_status(manifest)
package = build_proof_package(manifest)
package.save(Path("05_Results/proof_package.json"))
```

---

## 5. Frozen Parameters

All parameters are frozen before any data is observed.

| Parameter | Value | Contract |
|-----------|-------|----------|
| `alpha` | 0.01 | FROZEN_PARAMS.json |
| `sesoi_c_robust_sd` | 0.3 | FROZEN_PARAMS.json |
| `ci_level` | 0.99 | FROZEN_PARAMS.json |
| `n_steps` | 2600 | FROZEN_PARAMS.json |
| `intervention_point` | 900 | FROZEN_PARAMS.json |
| `intervention_duration` | 250 | FROZEN_PARAMS.json |
| `n_replicates` | 50 | FROZEN_PARAMS.json |
| `test_detection_rate_min` | 0.80 | FROZEN_PARAMS.json |
| `stable_fp_rate_max` | 0.20 | FROZEN_PARAMS.json |
| `placebo_fp_rate_max` | 0.20 | FROZEN_PARAMS.json |
| `max_indeterminate_rate` | 0.40 | FROZEN_PARAMS.json |
| `min_decidable_per_condition` | 6 | VALIDATION_DECIDABILITY.json |

**Calibration freeze**: `contracts/CALIBRATION_FREEZE.json`

---

## 6. Contract Inventory

| Contract | Purpose |
|----------|---------|
| `DUAL_PROOF_CONTRACT.json` | Dual proof acceptance gate schema |
| `FROZEN_PARAMS.json` | All frozen validation parameters |
| `SYNTHETIC_GATE_CONTRACT.json` | Synthetic gate requirement |
| `VALIDATION_BENCHMARK.json` | Fixed benchmark set with evidence levels |
| `VALIDATION_DECIDABILITY.json` | Decidability thresholds |
| `VALIDATION_SPECIFICITY.json` | Specificity objectives and contrast criterion |
| `VALIDATION_PRECHECKS.json` | Pre-check thresholds |
| `STABILITY_CRITERIA.json` | Stability criteria for real data |
| `FINAL_STATUS_SCHEMA.json` | Final status canonical schema (v2) |
| `PROOF_PACKAGE_SCHEMA.json` | Proof package schema |
| `CALIBRATION_FREEZE.json` | Calibration freeze record |
| `POWER_CRITERIA.json` | Power criteria for QCC analysis |
| `PLAN_SCHEMA.json` | Plan schema for pooling modes |

---

## 7. Framework Status Summary

After implementation of the 8 closure tickets:

- **Contractual coherence** (Tickets 1-4): Synthetic fallback enforced,
  canonical schema locked, summary/verdict alignment enforced,
  artifact audit automated.
- **Discriminant proof** (Tickets 5-7): Decidability KPIs explicit,
  multi-surrogate placebo battery deployed, frozen benchmark calibrated.
- **Closure documentation** (Ticket 8): This document.

### Definition of "Framework Complete"

```
dual_proof_status       = DUAL_PROOF_COMPLETE
final_pass              = true
summary ↔ verdict       = always aligned
validation_protocol     = ACCEPT
placebo battery         = passes (det_rate ≤ 0.20)
stable decidability     = majority decidable NOT_DETECTED
closure pack            = published
```

---

## 8. Changelog

| Date | Change |
|------|--------|
| 2026-03-08 | Initial closure pack (tickets 1-8) |
