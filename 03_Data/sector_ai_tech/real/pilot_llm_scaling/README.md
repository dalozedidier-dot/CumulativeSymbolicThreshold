# Pilot: LLM Scaling (AI/Technology)

**Pilot ID:** `sector_ai_tech.pilot_llm_scaling`
**Current level:** C (Exploratory)
**Upgrade target:** B (Conclusive)

## Research Question

Does the LLM capability trajectory exhibit a cumulative symbolic threshold
crossing consistent with emergent ability onset?

## Data Provenance

| Version | File | Source | N |
|---------|------|--------|---|
| Baseline | `real.csv` | Synthetic (Chinchilla/GPT calibrated) | 60 |
| Densified | `real_densified.csv` | Intra-family interpolation | 120 |

### Baseline (`real.csv`)
- **Source:** Synthetic data calibrated to published scaling laws
- **Status:** SYNTHETIC_CALIBRATED (not real benchmark data)
- **Range:** Simulated 2020-2026, monthly time steps
- **Columns:** t, O, R, I, demand, S

### Intermediate Variants
- `processed/real_family_core.csv` — Core families only (GPT + Claude + Llama)
- `processed/real_densified.csv` — Extended with consistent benchmark families

### Densified (`real_densified.csv`)
- **Method:** Intra-family interpolation on normalized index
- **Focus:** Double temporal depth from 60 to 120 monthly observations
- **Constraint:** Only include coherent model families, exclude contaminated benchmarks

## Proxy Mapping (Unchanged)

| Proxy | Physical quantity |
|-------|-------------------|
| O | Benchmark breadth (fraction of tasks solved) |
| R | Robustness to hard tasks (1 - failure rate) |
| I | Inter-benchmark coherence |
| demand | Parameter count (scaling pressure, log-normalized) |
| S | Cumulative emergent capabilities |

## Blocking Constraint

Series is 60 points total with ~30 per segment. Both segments fail
min_points_per_segment >= 60. This is a symmetric undersampling problem.

## Bias Risks

1. Heterogeneous benchmarks: MMLU saturation vs HumanEval sensitivity differ
2. Model family mixing: GPT vs Llama vs Claude have different scaling characteristics
3. Benchmark contamination: models may be trained on test sets (MMLU leakage)
4. Publication bias: only best models published, creating artificial monotonicity

## Contamination Exclusions

- Models with known MMLU test set leakage
- Task-specific fine-tuned models (instruction-tuned OK)
- Unreproducible benchmark scores (no public model weights)

## Directory Structure

```
pilot_llm_scaling/
  real.csv              # Canonical baseline (immutable)
  real_densified.csv    # Upgrade candidate
  proxy_spec.json       # Proxy definitions (unchanged)
  upgrade_plan.json     # Local upgrade contract
  raw/
    llm_scaling_original.csv    # Original data preserved
  processed/
    real_densified.csv          # Densified (120 pts)
    real_family_core.csv        # Core family variant
```
