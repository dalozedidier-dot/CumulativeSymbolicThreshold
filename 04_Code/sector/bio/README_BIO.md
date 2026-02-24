# Bio Sector Panel — ORI-C

## Scope

Biological systems: organisational, physiological, or epidemiological transitions
where a measurable phase shift occurs between a pre-threshold and a cumulative regime.

### Key conjecture in the bio domain

> When symbolic transmission — encoded biological information (immune memory, molecular
> chaperones, biodiversity indices, accumulated cellular stress response) — crosses a
> cumulative threshold, the system transitions from reactive/reversible to a
> self-reinforcing, partially irreversible state.

This is distinct from a simple dose-response.  T6 (symbolic cut / vaccination drop /
chaperone depletion) tests irreversibility: the system does not return to baseline
after the S channel is cut.

---

## Pilots

### 1. Epidemic / Contagion

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | 1 − case_fatality_rate | ECDC, OurWorldInData |
| R(t) | 1 − test_positivity_rate | ECDC |
| I(t) | 1 / (Rt + ε) | Rt.live, WHO |
| S(t) | vaccination_coverage | OurWorldInData |
| demand | new_cases_per_100k | ECDC |
| U(t) | lockdown / testing policy change | annotated manually |

**Public data:** https://ourworldindata.org/coronavirus
**Resolution:** weekly (recommended: 7-day rolling mean on daily series)
**Minimum rows:** 60 weeks

**What T1–T8 tests here:**
- T1: Variation in containment (O, R, I) predicts Cap → Σ gradient
- T2: Demand surge (case incidence) → Σ > 0 when D > Cap
- T3: High Σ (healthcare saturation) → V degrades
- T4: Variation in vaccination (S) → variation in C (intergenerational immunity gain)
- T5: Vaccination onset at t₀ → delayed C signal at horizon T
- T6: Vaccine rollback / waning → C drops without O/R/I change (irreversibility test)
- T7: Progressive vaccination coverage sweep → tipping point S* in C(t)
- T8: Multi-stress (epidemic wave + vaccine hesitancy + healthcare saturation) → causal coherence

---

### 2. Gene Expression / Cellular Stress

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | cell_viability | Flow cytometry / trypan blue |
| R(t) | HSP70 expression level | qPCR or Western blot time series |
| I(t) | transcription co-expression index | RNA-seq co-expression |
| S(t) | chaperone density | Proteomics / mass spec |
| demand | stress_intensity | Temperature / ROS measurements |

**Public data:** NCBI GEO (Gene Expression Omnibus) — search for heat-shock time series
**Example datasets:** GSE2052, GSE6798 (yeast heat shock), GSE152641 (COVID-19 immune)
**Resolution:** time-point series (typically 8–24 points; use interpolation to 50+ steps)

**Key ORI-C insight:**
- Cells maintain viability under stress via HSP70 and chaperone systems
- When cumulative chaperone density (S) crosses S*, cellular adaptive memory becomes self-reinforcing
- T6 test: remove stressor (cut demand) — C persists if cumulative threshold was crossed (irreversible adaptation)

---

### 3. Ecology: Predator-Prey / Ecosystem Tipping

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | prey_density_norm | Long-term ecological monitoring |
| R(t) | prey/pred stability index | Derived from count data |
| I(t) | habitat_connectivity | Landscape ecology databases |
| S(t) | species_diversity_index | GBIF, eBird, national surveys |
| demand | perturbation_intensity | Habitat loss / invasive species index |

**Public data:** LTER (Long-Term Ecological Research) network, GBIF, Living Planet Index
**Examples:** Mauna Loa CO₂ (context), Isle Royale wolf-moose series, British Moth Index
**Resolution:** annual (minimum 30 years)

**What makes ecology uniquely valuable for ORI-C:**
Regime shifts are well-documented (alternate stable states theory, Scheffer et al.).
ORI-C provides a mechanistic, pre-registerable framework for predicting *when* the shift occurs,
not just detecting it post-hoc.

---

## Generating synthetic data

```bash
# Epidemic pilot (250 steps)
python 04_Code/sector/bio/generate_synth.py \
    --pilot epidemic --outdir 05_Results/bio_synth/epidemic --seed 42

# Gene expression pilot
python 04_Code/sector/bio/generate_synth.py \
    --pilot geneexpr --outdir 05_Results/bio_synth/geneexpr --seed 42

# Ecology pilot
python 04_Code/sector/bio/generate_synth.py \
    --pilot ecology --outdir 05_Results/bio_synth/ecology --seed 42
```

## Running the bio sector suite

```bash
# Smoke CI run (synthetic, fast)
python 04_Code/sector/bio/run_sector_suite.py \
    --pilot-id epidemic --outdir 05_Results/sector_bio/run_001 --seed 1234

# With real data
python 04_Code/sector/bio/run_sector_suite.py \
    --pilot-id epidemic \
    --real-csv 03_Data/sector_bio/real/pilot_epidemic/real.csv \
    --outdir 05_Results/sector_bio/real_001 --seed 1234

# Full statistical mode
python 04_Code/sector/bio/run_sector_suite.py \
    --pilot-id epidemic --outdir 05_Results/sector_bio/full_001 \
    --seed 1234 --mode full_statistical --n-runs 100
```

## Mapping validity notes

The bio sector requires special attention to **circularity**:
- O, R, I must be independent measurements (not all derived from case counts alone)
- S must not be derived from C (vaccination coverage ≠ intergenerational gain)
- For gene expression: do not use the same gene sets in co-expression index and chaperone density

Fragility threshold: any proxy with `fragility_score > 0.60` should be flagged in the
manuscript as requiring sensitivity analysis on alternative proxy definitions.

---

## Scope statement

> Bio sector panel results prove the applicability of the ORI-C protocol to
> living biological systems with physiological or epidemiological transitions.
> All domain conclusions are conditional on a versioned proxy mapping (proxy_spec.json)
> and audited via sector_global_verdict.json. Indeterminate is informative, not failure.
