# Cosmo Sector Panel — ORI-C

## Scope

Astrophysical and cosmological systems: non-linear dynamical systems with regime transitions,
multi-scale processes, and event-rate changes detectable via observational time series.

### Why Cosmo is "living" in ORI-C's sense

Cosmo systems are not biologically alive but are **dynamically alive**: they exhibit
organisation (emission regularity), resilience (post-perturbation return), and integration
(multi-instrument coherence). The symbolic stock S(t) maps to **persistent structured signals**
— cumulative flare energy, burst memory, cycle-phase information.

The key Cosmo-specific discipline: **instrument change = symbolic cut (U(t))**.
A GOES → SDO transition, a photometry calibration gap, or a survey downtime is treated
as a controlled T6 perturbation. This is not a limitation — it is a natural
quasi-experimental design available only in the Cosmo domain.

---

## Pilots

### 1. Solar Activity Cycle

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | smoothed sunspot number | SIDC / NOAA SWPC |
| R(t) | 1 − Kp_max_monthly | NOAA SWPC (geomagnetic index) |
| I(t) | F10.7 solar radio flux | Dominion Radio Astrophysical Observatory |
| S(t) | cumulative flare energy index | GOES X-ray (NOAA) |
| demand | ap geomagnetic activity | NOAA SWPC |
| U(t) | GOES instrument transition dates | annotated manually |

**Public data:**
- NOAA SWPC: ftp://ftp.swpc.noaa.gov/pub/indices/
- SIDC: https://www.sidc.be/silso/datafiles
- Resolution: monthly (minimum 1 full 11-year cycle = 132 rows)

**What T1–T8 tests here:**
- T1: Sunspot → F10.7 → Kp gradient (Cap = O·R·I)
- T2: High ap demand → Σ > 0 during geomagnetic storm
- T3: High Σ (magnetospheric saturation) → V (cycle phase stability) degrades
- T4: Vary cumulative flare energy (S) → C (solar cycle gain) changes
- T5: Solar cycle ascending phase injection → delayed C at solar maximum
- T6: GOES instrument gap / calibration → C drops (symbolic cut test)
- T7: Progressive sunspot sweep → S* tipping point in cycle amplitude
- T8: Compound event (solar max + geomagnetic storm + instrument gap) → coherence check

---

### 2. Stellar Photometric Variability

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | photometric_stability | Kepler, TESS (MAST archive) |
| R(t) | post-flare flux recovery rate | Derived from light curve |
| I(t) | autocorrelation at rotation period | Derived from light curve |
| S(t) | cumulative flare energy above baseline | Derived |
| demand | long-term stellar variability trend | Derived |
| U(t) | instrument / aperture calibration gap | MAST header metadata |

**Public data:**
- MAST (Mikulski Archive): https://mast.stsci.edu/
  Kepler target pixels or light curves (API: `astroquery.mast`)
- Resolution: Kepler long cadence = 30-minute (use daily means for ORI-C)
- Recommended: M-dwarf flare stars (high flare rate), e.g. KIC 2157356

**Key Cosmo-specific test:**
T6 with instrument_gap=1 during Kepler quarterly roll or TESS sector gap.
Expected: C(t) drops during gap and either (a) recovers if pre-threshold,
or (b) does not fully recover if cumulative threshold was crossed.
This demonstrates irreversibility in a purely physical system.

---

### 3. Astrophysical Transient Rate

| ORI-C var | Proxy | Source |
|-----------|-------|--------|
| O(t) | survey rate regularity | ZTF alert stream (IPAC) |
| R(t) | rate return to baseline after burst | Derived |
| I(t) | multi-band count correlation | ZTF g/r band alert rates |
| S(t) | cumulative transient memory | Derived (above-baseline bursts) |
| demand | rolling mean alert rate | ZTF / LIGO/Virgo alert API |
| U(t) | planned survey downtime | ZTF scheduler log |

**Public data:**
- ZTF: https://www.ztf.caltech.edu/ (public alert stream via ALeRCE or Lasair)
- LIGO/Virgo: GWTC-3 public release (https://gwosc.org/)
- Resolution: daily alert counts (minimum 1 year = 365 rows)

---

## Generating synthetic data

```bash
python 04_Code/sector/cosmo/generate_synth.py \
    --pilot solar --outdir 05_Results/cosmo_synth/solar --seed 42

python 04_Code/sector/cosmo/generate_synth.py \
    --pilot stellar --outdir 05_Results/cosmo_synth/stellar --seed 42

python 04_Code/sector/cosmo/generate_synth.py \
    --pilot transient --outdir 05_Results/cosmo_synth/transient --seed 42
```

## Running the cosmo sector suite

```bash
# Smoke CI (default pilot: solar)
python 04_Code/sector/cosmo/run_sector_suite.py \
    --pilot-id solar --outdir 05_Results/sector_cosmo/run_001 --seed 1234

# Stellar with instrument gap stress test
python 04_Code/sector/cosmo/run_sector_suite.py \
    --pilot-id stellar --outdir 05_Results/sector_cosmo/stellar_001 --seed 1234
```

## Cosmo-specific mapping validity notes

1. **Instrument change annotation is mandatory.** Every transition between GOES
   generations, Kepler quarters, or ZTF observing periods must be marked in the
   `instrument_gap` column (= U(t) perturbation).

2. **Rolling window parameters are pre-registered.** The autocorrelation window
   (= stellar rotation period estimate), the burst threshold (transient pilot),
   and the flare accumulation rate (solar pilot) must all be fixed before data loading.

3. **Non-stationarity is expected and allowed.** Solar cycle data is
   non-stationary by construction. mapping_validator will flag ADF warnings —
   this is informative, not a REJECT condition for this domain.

4. **Multi-band coherence proxy.** For T8, use multi-instrument (radio + X-ray + optical)
   cross-correlation as the I(t) proxy to maximise independence from O and R.

---

## Scope statement

> Cosmo sector panel results prove the applicability of the ORI-C protocol to
> non-living dynamical systems with physically-driven regime transitions.
> Instrument transitions are treated as controlled symbolic-cut experiments (U(t)).
> All domain conclusions are conditional on versioned proxy mappings and
> audited via sector_global_verdict.json.
