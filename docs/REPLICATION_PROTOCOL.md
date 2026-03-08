# ORI-C Replication Protocol

**Version**: 1.0
**Date**: 2026-03-08

---

## Purpose

This document describes how an independent party can replicate the ORI-C
validation results using the frozen protocol and parameters.

---

## Prerequisites

1. Clone the repository
2. Python ≥ 3.11 with: `numpy`, `pandas`, `scipy`, `pytest`
3. No external data required for synthetic validation (data is generated)

---

## Step 1: Verify Frozen Parameters

```bash
cat contracts/FROZEN_PARAMS.json
```

Confirm the parameters match those documented in `docs/VALIDATION_CANONICAL_REPORT.md`.
**No parameter may be modified.**

---

## Step 2: Run the Validation Protocol

```bash
python 04_Code/pipeline/run_scientific_validation_protocol.py \
  --outdir replication_output \
  --n-replicates 50
```

This runs 150 synthetic simulations (50 × 3 conditions) and produces:
- `replication_output/tables/validation_summary.json`
- `replication_output/verdict.txt`
- `replication_output/VALIDATION_REPORT.md`

---

## Step 3: Verify the Outputs

### 3.1 Check the verdict
```bash
cat replication_output/verdict.txt
```

### 3.2 Check discrimination metrics
```bash
python -c "
import json
d = json.load(open('replication_output/tables/validation_summary.json'))
dm = d['discrimination_metrics']
print(f'Sensitivity: {dm[\"sensitivity\"]:.4f}')
print(f'Specificity: {dm[\"specificity\"]:.4f}')
print(f'Fisher p:    {dm[\"fisher_p_value\"]:.2e}')
print(f'Verdict:     {d[\"protocol_verdict\"]}')
"
```

### 3.3 Check decidability
```bash
python -c "
import json
d = json.load(open('replication_output/tables/validation_kpis.json'))
for cond in ('test', 'stable', 'placebo'):
    m = d['per_condition'][cond]
    print(f'{cond}: decidable={m[\"n_decidable\"]}/{m[\"n_total\"]} '
          f'({m[\"decidable_fraction\"]:.2f})')
"
```

---

## Step 4: Run the Test Suite

```bash
python -m pytest 04_Code/tests/ -v
```

All tests must pass.

---

## Step 5: Run the Artifact Audit

```bash
# Build manifest and final status first
python -c "
from pathlib import Path
from oric.proof_manifest import build_dual_proof_manifest, build_final_status
import json

m = build_dual_proof_manifest(
    synthetic_dir=Path('replication_output'),
    validation_dir=Path('replication_output'),
)
m.save(Path('replication_output/dual_proof_manifest.json'))
fs = build_final_status(m)
Path('replication_output/final_status.json').write_text(
    json.dumps(fs, indent=2, default=str)
)
"

# Run audit
python tools/audit_artifact_consistency.py --bundle-dir replication_output
```

---

## Expected Outcomes

With the frozen parameters and n=50 replicates:

| Condition | Expected |
|-----------|----------|
| Test detection rate | ≥ 0.80 |
| Stable detection rate (among decidable) | ≤ 0.20 |
| Placebo detection rate | Battery-dependent |
| Protocol verdict | ACCEPT (if all thresholds met) |

---

## What Constitutes Successful Replication

1. All tests pass
2. Protocol verdict matches (ACCEPT or same INDETERMINATE with documented reason)
3. Sensitivity and specificity within ±0.10 of reference values
4. Decidability fractions within ±0.15 of reference values
5. No artifact consistency errors

---

## Notes

- The protocol is **deterministic** given the seed_base (7000).
  Different Python/numpy versions may produce slightly different results
  due to floating-point differences.
- If the verdict is INDETERMINATE, check the decidability report for
  the specific conditions that failed.
- The adapted prechecks for stable regime are part of the frozen protocol
  and should not be modified during replication.
