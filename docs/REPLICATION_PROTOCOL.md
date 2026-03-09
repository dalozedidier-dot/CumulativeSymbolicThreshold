# ORI-C Replication Protocol

**Version**: 2.0
**Date**: 2026-03-09

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

## Step 6: Replicate the 7 Pilot Benchmarks

The pilot corpus is frozen in `contracts/FROZEN_PILOT_CORPUS.json`.

### 6.1 Run all pilot tests
```bash
python -m pytest 04_Code/tests/test_sector_pilots.py -v
python -m pytest 04_Code/tests/test_pilot_generalization.py -v
```

### 6.2 Verify generalization matrix
```bash
python -c "
import json
corpus = json.load(open('contracts/FROZEN_PILOT_CORPUS.json'))
print(f'Corpus version: {corpus[\"version\"]}')
print(f'Total pilots: {corpus[\"summary_table\"][\"total_pilots\"]}')
for p in corpus['pilots']:
    print(f'  {p[\"pilot_id\"]}: level={p[\"proof_level\"]}, '
          f'power={p[\"power_class\"]}, verdict={p[\"oric_verdict\"]}')
"
```

### 6.3 Expected pilot matrix

| Pilot | Level | Power | Verdict |
|-------|-------|-------|---------|
| EEG Bonn | B | adequate | ACCEPT |
| Solar | B | adequate | ACCEPT |
| COVID | B | borderline | ACCEPT |
| BTC | B | borderline | ACCEPT |
| Pantheon SN | C | borderline | INDETERMINATE |
| PBDB marine | C | borderline | INDETERMINATE |
| LLM scaling | C | underpowered | INDETERMINATE |

### 6.4 Run comparative benchmark
```bash
python -c "
from pathlib import Path
from oric.comparative_benchmark import run_all_benchmarks
results = run_all_benchmarks(Path('replication_output/benchmark'))
print(f'Benchmarked {results[\"total_pilots\"]} pilots across {len(results[\"methods\"])} methods')
"
```

---

## What Constitutes Successful Pilot Replication

1. All 7 pilot datasets load correctly (proxy_spec + CSV validation)
2. Generalization matrix matches frozen corpus (same levels, same verdicts)
3. Comparative benchmark runs on all available pilots
4. No reclassification without documented justification

---

## One-Command Replication (Recommended)

For a complete end-to-end replication, use the automated script:

```bash
# Full replication (tests + pilots + benchmark)
PYTHONPATH=src:04_Code python tools/replicate.py --outdir replication_output

# Fast replication (skip benchmark)
PYTHONPATH=src:04_Code python tools/replicate.py --outdir replication_output --fast

# Or via Makefile
make replicate
```

This script automatically:
1. Verifies frozen contract integrity (SHA-256 checksums)
2. Runs the complete test suite
3. Validates all 7 pilot datasets
4. Rebuilds and verifies the generalization matrix
5. Runs the comparative benchmark on 3 showcase pilots

Output: `replication_output/replication_summary.json`

---

## Step 7: Verify Densification Results

The 3 underpowered pilots have been densified. Verify the results:

```bash
PYTHONPATH=src:04_Code python 04_Code/pipeline/densify_underpowered_pilots.py \
  --outdir replication_output/power_upgrade
```

### 7.1 Expected densification outcomes

| Pilot | Original N | Densified N | Status | Best segmentation |
|-------|-----------|-------------|--------|-------------------|
| LLM scaling | 60 | 120 | conclusive | t=60 (signal=0.412) |
| Pantheon SN | 100 | 150 | conclusive | t=82 (signal=0.105) |
| PBDB marine | 100 | 140 | conclusive | t=70 (signal=0.060) |

**Important:** Densification via interpolation confirms structural compatibility
but does NOT constitute independent data extension. Level C pilots remain
indeterminate until real data augmentation is performed.

---

## Step 8: Verify Comparative Benchmark

Run the benchmark on 3 showcase pilots:

```bash
make benchmark-pilots
```

### 8.1 Expected benchmark results

| Pilot | ORI-C | CUSUM | Structural Break | Anomaly z-score | EWS |
|-------|-------|-------|-----------------|-----------------|-----|
| BTC | ACCEPT | detected | detected | detected | not detected |
| EEG Bonn | ACCEPT | detected | detected | detected | detected |
| Solar | ACCEPT | detected | detected | detected | not detected |

ORI-C agrees with 3-4/4 baselines on all pilots. ORI-C does not outperform
baselines on detection — its value is in structured multi-proxy semantics,
not raw detection power.

---

## Notes

- The protocol is **deterministic** given the seed_base (7000).
  Different Python/numpy versions may produce slightly different results
  due to floating-point differences.
- If the verdict is INDETERMINATE, check the decidability report for
  the specific conditions that failed.
- The adapted prechecks for stable regime are part of the frozen protocol
  and should not be modified during replication.
- The pilot corpus is versioned. Any change to pilot classifications
  requires a version bump in `FROZEN_PILOT_CORPUS.json`.
- The replication script (`tools/replicate.py`) can be run standalone
  with no prior knowledge of the project structure.
