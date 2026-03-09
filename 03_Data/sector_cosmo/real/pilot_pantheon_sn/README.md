# Pilot: Pantheon SN (Cosmology)

**Pilot ID:** `sector_cosmo.pilot_pantheon_sn`
**Current level:** C (Exploratory)
**Upgrade target:** B (Conclusive)

## Research Question

Does the SNe Ia distance-redshift relationship exhibit a cumulative symbolic
threshold crossing consistent with dark energy transition?

## Data Provenance

| Version | File | Source | N |
|---------|------|--------|---|
| Baseline | `real.csv` | Pantheon+ (Scolnic et al. 2022) | 100 |
| Densified | `real_densified.csv` | Interpolation in z-space (low-z focus) | 150 |

### Baseline (`real.csv`)
- **Source:** Pantheon+ SN Ia Hubble diagram, 100 redshift-ordered bins
- **Range:** z = 0.01 to z = 2.30
- **Columns:** t, z, mu_obs, mu_lcdm, O, R, I, demand, S

### Densified (`real_densified.csv`)
- **Method:** Linear interpolation in redshift space
- **Focus:** Low-z (pre-threshold) densification to reach min_points_per_segment >= 60
- **No new external data added** — interpolation only

## Proxy Mapping (Unchanged)

| Proxy | Physical quantity |
|-------|-------------------|
| O | Hubble residual dispersion |
| R | LCDM consistency |
| I | Cross-survey agreement |
| demand | Dark energy deviation |
| S | Cumulative SNe evidence |

## Blocking Constraint

Pre-threshold segment (~z < 0.05) has only ~35 data points.
Minimum required: 60 points per segment.

## Bias Risks

1. Low-z SNe from different surveys may have systematic calibration offsets
2. Interpolation between sparse bins may create artificial smoothness
3. Adding points in the gap region could bias toward detection

## Directory Structure

```
pilot_pantheon_sn/
  real.csv              # Canonical baseline (immutable)
  real_densified.csv    # Upgrade candidate
  proxy_spec.json       # Proxy definitions (unchanged)
  upgrade_plan.json     # Local upgrade contract
  raw/
    pantheon_original.csv   # Original data preserved
  processed/
    real_densified.csv      # Densified version
```
