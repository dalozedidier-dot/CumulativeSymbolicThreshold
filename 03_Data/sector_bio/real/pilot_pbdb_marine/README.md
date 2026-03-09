# Pilot: PBDB Marine (Paleobiology)

**Pilot ID:** `sector_bio.pilot_pbdb_marine`
**Current level:** C (Exploratory)
**Upgrade target:** B (Conclusive)

## Research Question

Does marine biodiversity exhibit a cumulative symbolic threshold crossing
at major mass extinction boundaries?

## Data Provenance

| Version | File | Source | N |
|---------|------|--------|---|
| Baseline | `real.csv` | PBDB stage-level bins | 100 |
| Densified | `real_densified.csv` | 5-Myr bins (Cenozoic refinement) | 140 |

### Baseline (`real.csv`)
- **Source:** Paleobiology Database, marine metazoan genus diversity
- **Range:** 541 Ma to present, ~100 geological stage bins
- **Columns:** t, Ma, genera, extinction_rate, origination_rate, O, R, I, demand, S

### Intermediate Variants
- `processed/real_binning_stage.csv` — Original stage-level (100 pts, baseline)
- `processed/real_binning_10myr.csv` — 10-Myr uniform bins (110 pts)
- `processed/real_binning_5myr.csv` — 5-Myr uniform bins (140 pts, = densified)

### Densified (`real_densified.csv`)
- **Method:** Temporal bin refinement in Cenozoic (finer resolution where stages are long)
- **Focus:** Post-extinction recovery (66-0 Ma) where geological stages span 10-20 Myr
- **No new external data added** — re-binning of existing PBDB data

## Proxy Mapping (Unchanged)

| Proxy | Physical quantity |
|-------|-------------------|
| O | Sampled genus diversity |
| R | 1 - extinction_rate (resilience) |
| I | Origination rate (integration) |
| demand | Extinction rate (external stress) |
| S | Cumulative diversity above minimum |

## Blocking Constraint

Post-threshold segment (Cenozoic recovery after K-Pg, 66-0 Ma) has only
~40 data points due to long geological stages. Minimum required: 60.

## Bias Risks

1. Finer Cenozoic bins increase resolution asymmetrically (Pull of the Recent)
2. 5-Myr bins in Cenozoic vs stage-level in Paleozoic creates temporal heterogeneity
3. Sampling standardization (SQS/CR) may change diversity estimates vs raw counts

## Directory Structure

```
pilot_pbdb_marine/
  real.csv              # Canonical baseline (immutable)
  real_densified.csv    # Upgrade candidate
  proxy_spec.json       # Proxy definitions (unchanged)
  upgrade_plan.json     # Local upgrade contract
  raw/
    pbdb_original.csv       # Original data preserved
  processed/
    real_densified.csv      # Densified (140 pts)
    real_binning_stage.csv  # Stage-level baseline
    real_binning_10myr.csv  # 10-Myr intermediate
    real_binning_5myr.csv   # 5-Myr target
```
