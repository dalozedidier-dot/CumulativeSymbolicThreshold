# Infra Sector Panel — ORI-C

## Scope

Socio-technical and critical infrastructure systems: electrical grids, transport networks,
and macro-financial systems. These are ORI-C's "natural domain" — highly instrumented,
with documented perturbations (N-1 events, incidents, policy decisions) that serve as
near-experimental U(t) inputs.

### Key conjecture in the infra domain

> When demand-response memory (grid), adaptive routing (traffic), or policy credibility
> (finance) accumulate past a critical threshold S*, the infrastructure system transitions
> from a reactive, demand-following regime to a self-organizing, demand-shaping regime.
> This transition is measurable, falsifiable, and has direct operational implications.

---

## Pilots

### 1. Electrical Grid

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | 1 − frequency_deviation | ENTSO-E Transparency / EIA |
| R(t) | reserve_margin | ENTSO-E Generation capacity |
| I(t) | cross-border flow coherence | ENTSO-E Cross-border flows |
| S(t) | demand_response_index | ENTSO-E / TSO reports |
| demand | total_load_norm | ENTSO-E Actual Load |
| U(t) | N-1 events, heat waves, cold snaps | ENTSO-E Outage data |

**Public data:**
- ENTSO-E Transparency: https://transparency.entsoe.eu/
  (API via entsoe-py: `pip install entsoe-py`)
- EIA (US grid): https://www.eia.gov/electricity/data/
- Resolution: 15-minute preferred, hourly minimum
- Minimum rows: 168 (1 week) for smoke CI; 8760 (1 year) for full statistical run

**What T1–T8 tests here:**
- T1: Reserve margin variation → Cap variation
- T2: Load surge (heat wave) → Σ > 0 when demand > Cap
- T3: High Σ (scarcity events) → V (grid viability) degrades
- T4: Vary DR participation → C (demand-shaping gain) varies
- T5: DR programme launch → delayed C signal at horizon T
- T6: DR withdrawal / programme cancellation → C drops
- T7: Progressive DR deployment → S* tipping point
- T8: Multi-stress (heat wave + generator outage + cross-border congestion) → coherence

---

### 2. Traffic Network

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | speed_ratio (free/current) | TOMTOM Traffic Index, HERE, Waze |
| R(t) | post-incident speed recovery | Derived from loop detector data |
| I(t) | parallel route correlation | Derived from multi-route sensors |
| S(t) | routing_information_density | GPS probe vehicle data / FCD |
| demand | total_network_load | Loop detector counts |
| U(t) | documented incidents, closures | Highway authority incident logs |

**Public data:**
- TOMTOM Traffic Index: https://www.tomtom.com/traffic-index/
- UK INRIX / Highways England incident data (public access with registration)
- OpenStreetMap + OSMnx for network topology
- Resolution: 5-minute or 15-minute (use hourly means for ORI-C)

**Key infra-specific test:**
T6 with routing information cut (GPS blackout / congestion pricing removal):
tests whether C(t) drops when the symbolic routing channel is disabled.
In practice: use before/after comparison of GPS navigation availability (rural vs urban).

---

### 3. Finance Macro

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | 1 / (1 + 10·implied_vol) | CBOE VIX / VSTOXX |
| R(t) | liquidity_index | BIS bid-ask spread composite |
| I(t) | equity-bond correlation | Derived from daily returns |
| S(t) | policy_credibility_index | Central bank communication index |
| demand | investment_grade_spread | ICE BofA OAS indices (FRED) |
| U(t) | policy decision dates (FOMC/ECB) | Official calendars |

**Public data:**
- FRED: https://fred.stlouisfed.org/ (VIX, BAMLC0A0CM, MOVE, etc.)
- BIS quarterly review data
- ECB Statistical Data Warehouse
- Resolution: daily (use weekly or monthly means for stable statistics)

**Note:** The finance pilot is methodologically equivalent to the canonical FRED
monthly pilot but adds explicit U(t) policy event annotation and uses the full
ORI-C proxy mapping structure. The `infra_finance_synth` synthetic pilot provides
a controlled environment; real-data runs use FRED series with locked download timestamps.

---

## Generating synthetic data

```bash
python 04_Code/sector/infra/generate_synth.py \
    --pilot grid --outdir 05_Results/infra_synth/grid --seed 42

python 04_Code/sector/infra/generate_synth.py \
    --pilot traffic --outdir 05_Results/infra_synth/traffic --seed 42

python 04_Code/sector/infra/generate_synth.py \
    --pilot finance --outdir 05_Results/infra_synth/finance --seed 42
```

## Running the infra sector suite

```bash
# Smoke CI (default pilot: grid)
python 04_Code/sector/infra/run_sector_suite.py \
    --pilot-id grid --outdir 05_Results/sector_infra/run_001 --seed 1234

# Finance with real FRED data
python 04_Code/sector/infra/run_sector_suite.py \
    --pilot-id finance \
    --real-csv 03_Data/real/fred_monthly/real.csv \
    --outdir 05_Results/sector_infra/finance_fred_001 --seed 1234
```

## Infra-specific mapping validity notes

1. **Manipulability is high for S(t).** Policy credibility (finance), demand response
   (grid), and routing information (traffic) can all be directly influenced by market
   participants or operators. This does not invalidate the proxy but requires
   `manipulability_note` to be filled in and a secondary sensitivity analysis.

2. **U(t) annotation is mandatory.** Infra systems have documented perturbation events
   (FOMC decisions, N-1 contingency incidents, traffic closures). These must be annotated
   in the `U` column before running. Unannotated shocks confound T2/T3 interpretation.

3. **Structural breaks.** Financial series cross regulatory regime changes (Basel III,
   QE programmes). Mark these as U(t) events with `perturbation_type = "structural_break"`.

4. **Resolution considerations.** Grid data at 15-min resolution is different from
   weekly financial data. Do not compare absolute correlation values across sectors.
   The protocol is resolution-agnostic — what matters is the relative ORI dynamics.

---

## Cross-sector scope statement

> The canonical CI suite proves reproducibility of the protocol.
> Bio / Cosmo / Infra sector suites prove applicability to non-stationary,
> multi-scale systems with exogenous perturbations.
> All domain conclusions are conditional on a versioned, audited proxy mapping (proxy_spec.json).
> Indeterminate verdicts are informative — they identify proxy or data quality limitations,
> not protocol failures.
