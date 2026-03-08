# ORI-C Validation Protocol — Canonical Report

**Schema**: `oric.validation_report.v1`
**Date**: 2026-03-08

---

## Protocol Design

The ORI-C scientific validation protocol is a three-arm controlled
experiment designed to prove that the framework can discriminate between
genuine regime transitions and null conditions.

### Arms

| Arm | Description | Ground Truth | Expected Verdict |
|-----|-------------|--------------|------------------|
| **TEST** | Demand shock at t=900, duration=250 | Transition exists | DETECTED |
| **STABLE** | No intervention, identical trajectories | No transition | NOT_DETECTED |
| **PLACEBO** | Multi-surrogate battery (5 strategies) | No aligned transition | NOT_DETECTED |

### Metrics

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| Sensitivity | ≥ 0.80 | Fraction of TEST runs correctly detected |
| Specificity | ≥ 0.80 | Fraction of negative controls correctly not detected |
| Fisher p | < 0.01 | Independence test for condition × verdict |
| Indeterminate rate | < 0.40 per condition | Protocol can decide |

### Verdict Rule

```
ACCEPT  if: sensitivity ≥ 0.80 AND specificity ≥ 0.80 AND Fisher p < 0.01
            AND indeterminate rate < 0.40 per condition
REJECT  if: sensitivity < 0.60 OR specificity < 0.60
INDETERMINATE otherwise
```

---

## Placebo Battery (v2)

The placebo battery replaces the original single cyclic-shift with 5
structurally diverse strategies:

| Strategy | Preserves | Destroys |
|----------|-----------|----------|
| `cyclic_shift` | Autocorrelation, spectral density | Temporal alignment |
| `temporal_permute` | Marginal distribution | Autocorrelation, temporal alignment |
| `phase_randomize` | Spectral density | Phase coupling, temporal alignment |
| `proxy_remap` | Autocorrelation, temporal alignment | Cross-correlation, causal mapping |
| `block_shuffle` | Local autocorrelation | Global temporal structure |

**Battery passes** if detection rate across all strategies ≤ 20%.

---

## Decidability KPIs

Each condition reports:

- `decidable_count` / `n_total`
- `decidable_fraction`
- `indeterminate_rate`
- `indeterminate_reasons` (taxonomy with counts)
- `top_indeterminate_reason`

The key phrase to achieve:
> "On stable, the protocol decides majority NOT_DETECTED"

### Adapted Prechecks for Stable Regime

| Parameter | Standard | Stable-adapted |
|-----------|----------|----------------|
| `min_unique_values_C` | 5 | 3 |
| `min_variance_C` | 1e-10 | 1e-15 |
| `min_points_per_segment` | 60 | max(30, n/5) |

Rationale: stable data has near-zero C variance by design.

---

## Frozen Parameters

All parameters frozen before data observation.
Source: `contracts/FROZEN_PARAMS.json`

```json
{
  "alpha": 0.01,
  "n_steps": 2600,
  "intervention_point": 900,
  "intervention_duration": 250,
  "n_replicates": 50,
  "seed_base": 7000,
  "test_detection_rate_min": 0.80,
  "stable_fp_rate_max": 0.20,
  "placebo_fp_rate_max": 0.20,
  "max_indeterminate_rate": 0.40,
  "min_decidable_per_condition": 6
}
```

---

## Benchmark Set

Fixed inputs (never cherry-picked):

| ID | Category | n (approx) | Expected |
|----|----------|-----------|----------|
| `fred_monthly` | Economic | 480 | ACCEPT |
| `epidemic_ecdc_BE` | Biological | 350 | null |
| `excess_deaths_OWID_BE` | Biological | 4500 | null |
| `ecology_pelt` | Ecological | varies | null |

Source: `contracts/VALIDATION_BENCHMARK.json`

---

## How to Run

```bash
# Full validation (50 replicates, ~5 minutes)
python 04_Code/pipeline/run_scientific_validation_protocol.py \
  --outdir 05_Results/scientific_validation --n-replicates 50

# Quick CI check (5 replicates, ~10 seconds)
python -m pytest 04_Code/tests/test_validation_protocol_reference_benchmark.py -v
```

---

## Output Files

| File | Content |
|------|---------|
| `tables/validation_summary.json` | Full protocol output with all metrics |
| `tables/validation_results.csv` | Per-replicate results |
| `tables/validation_kpis.json` | Decidability KPIs |
| `tables/failure_report.csv` | Anomalous cases |
| `VALIDATION_REPORT.md` | Human-readable report |
| `verdict.txt` | ACCEPT / REJECT / INDETERMINATE |
| `frozen_params.json` | Copy of frozen parameters used |
