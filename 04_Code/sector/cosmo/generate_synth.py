#!/usr/bin/env python3
"""04_Code/sector/cosmo/generate_synth.py

Synthetic time series for the cosmology/astrophysics sector pilots.

Pilots: solar, stellar, transient

Design constraints: stationary AR(1) proxies, low pairwise collinearity,
mid-series demand shock to trigger C transition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_PILOT_CONFIGS: dict[str, dict] = {
    "solar": {
        # Solar cycle monitoring system
        "O": {"phi": 0.80, "mu": 0.56, "sigma": 0.038},   # solar activity index
        "R": {"phi": 0.91, "mu": 0.62, "sigma": 0.016},   # instrument redundancy
        "I": {"phi": 0.60, "mu": 0.51, "sigma": 0.048},   # multi-wavelength integration
        "demand_base_ratio": 0.83,
        "shock_factor": 1.25,
        "shock_start_frac": 0.32,
        "shock_end_frac": 0.63,
    },
    "stellar": {
        # Stellar population analysis pipeline
        "O": {"phi": 0.75, "mu": 0.54, "sigma": 0.042},   # data completeness rate
        "R": {"phi": 0.89, "mu": 0.65, "sigma": 0.018},   # pipeline robustness score
        "I": {"phi": 0.55, "mu": 0.57, "sigma": 0.052},   # cross-catalog integration
        "demand_base_ratio": 0.81,
        "shock_factor": 1.27,
        "shock_start_frac": 0.30,
        "shock_end_frac": 0.60,
    },
    "transient": {
        # Transient event detection network
        "O": {"phi": 0.78, "mu": 0.58, "sigma": 0.036},   # detection efficiency
        "R": {"phi": 0.92, "mu": 0.60, "sigma": 0.014},   # network redundancy
        "I": {"phi": 0.63, "mu": 0.53, "sigma": 0.046},   # alert-system integration
        "demand_base_ratio": 0.85,
        "shock_factor": 1.23,
        "shock_start_frac": 0.35,
        "shock_end_frac": 0.65,
    },
}


def generate(pilot_id: str, seed: int, n_steps: int) -> pd.DataFrame:
    """Generate a synthetic panel for the given cosmo pilot."""
    if pilot_id not in _PILOT_CONFIGS:
        raise ValueError(f"Unknown cosmo pilot: {pilot_id!r}. Choose from {sorted(_PILOT_CONFIGS)}")

    cfg = _PILOT_CONFIGS[pilot_id]
    rng = np.random.default_rng(int(seed))
    t = np.arange(int(n_steps), dtype=int)
    cap_scale = 1_000.0

    def _ar1(phi: float, mu: float, sigma: float, n: int) -> np.ndarray:
        x = np.empty(n)
        x[0] = mu + rng.normal(0.0, sigma)
        for i in range(1, n):
            x[i] = mu + phi * (x[i - 1] - mu) + rng.normal(0.0, sigma)
        return np.clip(x, 0.02, 0.98)

    O = _ar1(**cfg["O"], n=int(n_steps))
    R = _ar1(**cfg["R"], n=int(n_steps))
    I = _ar1(**cfg["I"], n=int(n_steps))

    Cap = O * R * I * cap_scale
    base_demand = cfg["demand_base_ratio"] * Cap

    shock_start = int(cfg["shock_start_frac"] * n_steps)
    shock_end = int(cfg["shock_end_frac"] * n_steps)
    shock_mask = (t >= shock_start) & (t < shock_end)

    demand_noise = rng.normal(0.0, 0.02 * base_demand.mean(), size=int(n_steps))
    demand = base_demand + demand_noise
    demand[shock_mask] *= float(cfg["shock_factor"])

    return pd.DataFrame({"t": t, "O": O, "R": R, "I": I, "demand": demand})
"""generate_synth.py — Synthetic data generator for the Cosmo sector panel.

Three pilots:

  solar     : Solar activity cycle — sunspot number, F10.7, geomagnetic Kp
              Regime transition: solar minimum → ascending phase → solar maximum
              Perturbation: sudden geomagnetic storm (symbolic cut = observation gap
                            or instrument saturation event)

  stellar   : Stellar photometric variability (Kepler-like)
              Regime change: quiescent → flare-active state
              Perturbation: instrument change / data gap (standard Cosmo stress test)

  transient : Astrophysical transient rate (ZTF-like alert stream)
              Regime shift: low-rate background → burst episode
              Perturbation: survey downtime → symbolic cut in detection channel

ORI-C mapping is scale-agnostic:
  O(t) = organisational regularity of the source
  R(t) = resilience: return to baseline after perturbation
  I(t) = integration: multi-instrument / multi-wavelength coherence
  S(t) = symbolic stock: cumulative structured signal (persistent pattern density)
  demand(t) = exogenous load on the detection / observation system

Key discipline: "instrument change" is treated as a U(t) symbolic cut,
identical in protocol to a vaccination programme cut in bio.  This is the
Cosmo-specific stress test that validates T6 in this domain.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Solar activity cycle
# --------------------------------------------------------------------------- #

def _generate_solar(n: int, seed: int) -> pd.DataFrame:
    """Simulate a solar activity cycle with instrument-change perturbation."""
    rng = np.random.default_rng(seed)

    # ~11-year solar cycle compressed to n steps
    cycle_period = n * 0.7
    t_arr = np.arange(n)

    # Sunspot number proxy (normalised)
    phase = 2 * np.pi * t_arr / cycle_period
    sunspot_base = 0.5 * (1 + np.sin(phase - np.pi / 2))
    sunspot = np.clip(sunspot_base + rng.normal(0, 0.04, n), 0, 1)

    # Solar radio flux F10.7 (tightly correlated with sunspots, small lead)
    f107 = np.roll(sunspot_base, -3) + rng.normal(0, 0.03, n)
    f107 = np.clip(f107, 0, 1)

    # Geomagnetic activity Kp index (higher during solar max, spiky)
    kp = sunspot_base * 0.6 + rng.exponential(0.08, n)
    kp = np.clip(kp / kp.max(), 0, 1)

    # ORI proxies
    # O: regularity of solar emission (inverse of short-term variance)
    O_arr = np.zeros(n)
    W = 12
    for t in range(W, n):
        O_arr[t] = 1.0 / (1.0 + sunspot[t-W:t].std())
    O_arr[:W] = O_arr[W]

    # R: magnetic resilience — how quickly field recovers after storm
    storm_t = n // 2   # major geomagnetic storm
    R_arr = np.ones(n)
    R_arr[storm_t:storm_t + 20] = np.linspace(1.0, 0.2, 20)
    R_arr[storm_t + 20:storm_t + 50] = np.linspace(0.2, 0.85, 30)
    R_arr[storm_t + 50:] = 0.85
    R_arr += rng.normal(0, 0.025, n)
    R_arr = np.clip(R_arr, 0, 1)

    # I: multi-instrument coherence (F10.7 ↔ Kp correlation)
    I_arr = np.zeros(n)
    W2 = 20
    for t in range(W2, n):
        r = np.corrcoef(f107[t-W2:t], kp[t-W2:t])[0, 1]
        I_arr[t] = (abs(r) if np.isfinite(r) else 0.0)
    I_arr[:W2] = I_arr[W2]

    # S: cumulative structured solar signal (symbolic stock)
    # Persistent "memory" of cycle phase: integrated energy above threshold
    THRESHOLD = 0.45
    S_arr = np.zeros(n)
    for t in range(1, n):
        injection = max(sunspot[t] - THRESHOLD, 0) * 0.08
        decay     = 0.003 * S_arr[t-1]
        S_arr[t]  = np.clip(S_arr[t-1] + injection - decay + rng.normal(0, 0.003), 0, 1)

    # Instrument change (symbolic cut): gap at 3/4 of series
    gap_start = 3 * n // 4
    gap_len   = min(15, n - gap_start)
    sunspot[gap_start:gap_start+gap_len] = np.nan
    f107[gap_start:gap_start+gap_len]    = np.nan
    # Forward-fill for ORI computation; gap marker kept separately
    gap_mask = np.zeros(n)
    gap_mask[gap_start:gap_start+gap_len] = 1.0

    def norm01(x):
        x = np.where(np.isfinite(x), x, np.nanmean(x))
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":              t_arr,
        "O":              norm01(O_arr),
        "R":              norm01(R_arr),
        "I":              norm01(I_arr),
        "S":              norm01(S_arr),
        "demand":         norm01(kp),
        "sunspot_raw":    sunspot,
        "f107_raw":       f107,
        "kp_raw":         kp,
        "instrument_gap": gap_mask,   # marks symbolic cut event
    })
    return df


_PROXY_SPEC_SOLAR = {
    "dataset_id":    "cosmo_solar_synth",
    "sector":        "cosmo",
    "pilot":         "solar",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "perturbation_column": "instrument_gap",
    "perturbation_type":   "symbolic_cut",
    "perturbation_note":   (
        "instrument_gap=1 marks a data gap / instrument saturation event "
        "analogous to a symbolic cut U(t). T6 tests C(t) drop during this window."
    ),
    "columns": [
        {
            "oric_role":           "O",
            "source_column":       "O",
            "direction":           "positive",
            "fragility_score":     0.30,
            "fragility_note":      "Regularity index depends on rolling window choice",
            "manipulability_note": "Not manipulable — derived from physical measurement",
            "description":         "Emission regularity (inverse short-term variability of sunspot proxy)",
        },
        {
            "oric_role":           "R",
            "source_column":       "R",
            "direction":           "positive",
            "fragility_score":     0.35,
            "fragility_note":      "Storm recovery timescale is model-dependent",
            "manipulability_note": "Not directly manipulable",
            "description":         "Magnetic resilience: post-storm recovery rate",
        },
        {
            "oric_role":           "I",
            "source_column":       "I",
            "direction":           "positive",
            "fragility_score":     0.50,
            "fragility_note":      "Rolling correlation sensitive to window size and data gaps",
            "manipulability_note": "Gap imputation choice affects integration index",
            "description":         "Multi-instrument coherence: F10.7 ↔ Kp rolling correlation",
        },
        {
            "oric_role":           "S",
            "source_column":       "S",
            "direction":           "positive",
            "fragility_score":     0.30,
            "fragility_note":      "Threshold for 'active' solar state is subjective",
            "manipulability_note": "Cumulation rate depends on threshold parameter (pre-registered)",
            "description":         "Cumulative solar structured signal above activity threshold",
        },
        {
            "oric_role":           "demand",
            "source_column":       "demand",
            "direction":           "positive",
            "fragility_score":     0.25,
            "fragility_note":      "Kp index is a global average; local effects can differ",
            "manipulability_note": "Not manipulable — measured by magnetometer network",
            "description":         "Geomagnetic Kp index (normalised) — environmental demand",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Stellar photometric variability
# --------------------------------------------------------------------------- #

def _generate_stellar(n: int, seed: int) -> pd.DataFrame:
    """Simulate Kepler-like photometry: quiescent → flare-active state."""
    rng = np.random.default_rng(seed)

    t_arr = np.arange(n)
    flare_onset = n // 3

    # Base flux (normalised): slowly decreasing trend + periodic pulsation
    rotation_period = 27
    flux_base = 1.0 - 0.002 * t_arr / n + 0.01 * np.sin(2 * np.pi * t_arr / rotation_period)

    # Flares: Poisson-sampled, each a fast rise + exponential decay
    flux = flux_base.copy() + rng.normal(0, 0.003, n)
    flare_rate_pre  = 0.02   # flares per step before onset
    flare_rate_post = 0.12   # flares per step after onset
    for t in range(n):
        rate = flare_rate_post if t >= flare_onset else flare_rate_pre
        if rng.random() < rate:
            amplitude = rng.exponential(0.04)
            duration  = int(rng.exponential(8)) + 2
            for dt in range(min(duration, n - t)):
                flux[t + dt] = flux[t + dt] + amplitude * np.exp(-dt / 3.0)

    # ORI proxies
    # O: photometric stability (inverse of short-term scatter)
    O_arr = np.zeros(n)
    W = 15
    for tt in range(W, n):
        O_arr[tt] = 1.0 / (1.0 + flux[tt-W:tt].std())
    O_arr[:W] = O_arr[W]

    # R: resilience = how quickly flux returns to baseline after flare
    R_arr = np.zeros(n)
    rolling_median = np.zeros(n)
    for tt in range(W, n):
        rolling_median[tt] = np.median(flux[tt-W:tt])
    rolling_median[:W] = rolling_median[W]
    R_arr = 1.0 - np.abs(flux - rolling_median) / (rolling_median + 1e-9)
    R_arr = np.clip(R_arr, 0, 1)

    # I: spectral coherence (rolling autocorrelation at lag=rotation_period)
    I_arr = np.zeros(n)
    W3 = 2 * rotation_period
    for tt in range(W3, n):
        seg = flux[tt-W3:tt]
        if len(seg) > rotation_period:
            c = np.corrcoef(seg[:-rotation_period], seg[rotation_period:])[0, 1]
            I_arr[tt] = abs(c) if np.isfinite(c) else 0.0
    I_arr[:W3] = I_arr[W3]

    # S: persistent flare memory (cumulative flare energy above baseline)
    EXCESS_THR = 0.015
    S_arr = np.zeros(n)
    for tt in range(1, n):
        excess = max(flux[tt] - rolling_median[tt] - EXCESS_THR, 0)
        decay  = 0.008 * S_arr[tt-1]
        S_arr[tt] = np.clip(S_arr[tt-1] + 0.1 * excess - decay + rng.normal(0, 0.003), 0, 1)

    # Instrument change at 2/3 of series
    instr_t = 2 * n // 3
    instr_mask = np.zeros(n)
    instr_mask[instr_t:instr_t+10] = 1.0   # 10-step calibration gap
    flux[instr_t:instr_t+10]       = np.nan

    def norm01(x):
        x = np.where(np.isfinite(x), x, np.nanmean(x))
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":              t_arr,
        "O":              norm01(O_arr),
        "R":              norm01(R_arr),
        "I":              norm01(I_arr),
        "S":              norm01(S_arr),
        "demand":         norm01(np.abs(flux_base - np.nanmean(flux_base))),
        "flux_raw":       flux,
        "instrument_gap": instr_mask,
    })
    return df


_PROXY_SPEC_STELLAR = {
    "dataset_id":    "cosmo_stellar_synth",
    "sector":        "cosmo",
    "pilot":         "stellar",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "perturbation_column": "instrument_gap",
    "perturbation_type":   "symbolic_cut",
    "perturbation_note":   (
        "instrument_gap=1 marks aperture photometry calibration gap "
        "(instrument change standard stress test for Cosmo panel)."
    ),
    "columns": [
        {
            "oric_role": "O", "source_column": "O", "direction": "positive",
            "fragility_score": 0.35,
            "fragility_note": "Photometric scatter depends on aperture and sky background",
            "manipulability_note": "Not manipulable; depends on telescope aperture and detector",
            "description": "Photometric stability (inverse short-term flux scatter)",
        },
        {
            "oric_role": "R", "source_column": "R", "direction": "positive",
            "fragility_score": 0.30,
            "fragility_note": "Baseline depends on rolling window; flare detection threshold matters",
            "manipulability_note": "Not manipulable",
            "description": "Post-flare flux return to baseline (resilience)",
        },
        {
            "oric_role": "I", "source_column": "I", "direction": "positive",
            "fragility_score": 0.55,
            "fragility_note": "Rotation period must be pre-specified; uncertain for rapid rotators",
            "manipulability_note": "Autocorrelation window is a pre-registered parameter",
            "description": "Spectral coherence at stellar rotation period (integration)",
        },
        {
            "oric_role": "S", "source_column": "S", "direction": "positive",
            "fragility_score": 0.40,
            "fragility_note": "Cumulation rate and excess threshold are pre-registered",
            "manipulability_note": "Post-hoc threshold change would require new pre-registration",
            "description": "Cumulative flare energy above baseline (symbolic stock)",
        },
        {
            "oric_role": "demand", "source_column": "demand", "direction": "positive",
            "fragility_score": 0.25,
            "fragility_note": "Long-term trend proxy; requires stable photometric calibration",
            "manipulability_note": "Secular trend component depends on detrending method",
            "description": "Long-term stellar variability trend (environmental demand)",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Transient rate (ZTF-like)
# --------------------------------------------------------------------------- #

def _generate_transient(n: int, seed: int) -> pd.DataFrame:
    """Simulate astrophysical transient alert rate: background → burst episode."""
    rng = np.random.default_rng(seed)
    t_arr = np.arange(n)

    # Poisson rate: background with burst episode
    burst_start = n // 3
    burst_end   = n // 2
    base_rate   = 3.0    # alerts per step
    burst_rate  = 18.0

    rate = np.where(
        (t_arr >= burst_start) & (t_arr < burst_end),
        burst_rate + rng.normal(0, 1, n),
        base_rate + rng.exponential(0.5, n),
    )
    rate = np.maximum(rate, 0)

    # Alert counts
    counts = rng.poisson(rate)

    # Survey downtime (symbolic cut): gap in observation
    survey_gap_t = 3 * n // 4
    survey_mask  = np.zeros(n)
    survey_mask[survey_gap_t:survey_gap_t+20] = 1.0
    counts_obs   = counts.copy().astype(float)
    counts_obs[survey_gap_t:survey_gap_t+20] = np.nan

    # Rolling statistics
    W = 20
    rolling_mean = np.zeros(n)
    rolling_std  = np.zeros(n)
    for tt in range(W, n):
        seg = counts_obs[max(tt-W,0):tt]
        seg = seg[np.isfinite(seg)]
        if len(seg) > 1:
            rolling_mean[tt] = seg.mean()
            rolling_std[tt]  = seg.std()
    rolling_mean[:W] = rolling_mean[W] if rolling_mean[W] > 0 else base_rate
    rolling_std[:W]  = rolling_std[W]

    # ORI proxies
    # O: survey regularity (inverse of rate variability)
    O_arr = 1.0 / (1.0 + rolling_std / (rolling_mean + 1e-9))

    # R: baseline stability — does rate return after burst?
    R_arr = np.zeros(n)
    for tt in range(1, n):
        dev = abs(rolling_mean[tt] - base_rate) / (base_rate + 1e-9)
        R_arr[tt] = 1.0 / (1.0 + dev)

    # I: multi-band coherence proxy (rolling correlation of rate sub-samples)
    counts_a = rng.binomial(counts, 0.6)   # "band a"
    counts_b = counts - counts_a           # "band b"
    I_arr = np.zeros(n)
    for tt in range(W, n):
        a = counts_a[tt-W:tt].astype(float)
        b = counts_b[tt-W:tt].astype(float)
        c = np.corrcoef(a, b)[0, 1]
        I_arr[tt] = abs(c) if np.isfinite(c) else 0.0
    I_arr[:W] = I_arr[W]

    # S: cumulative transient signal (persistent event memory)
    S_arr = np.zeros(n)
    BURST_THR = base_rate * 1.5
    for tt in range(1, n):
        c = counts_obs[tt] if np.isfinite(counts_obs[tt]) else 0.0
        injection = max(c - BURST_THR, 0) * 0.015
        decay     = 0.005 * S_arr[tt-1]
        S_arr[tt] = np.clip(S_arr[tt-1] + injection - decay + rng.normal(0, 0.004), 0, 1)

    def norm01(x):
        x = np.where(np.isfinite(x), x, np.nanmean(x) if np.any(np.isfinite(x)) else 0.0)
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":            t_arr,
        "O":            norm01(O_arr),
        "R":            norm01(R_arr),
        "I":            norm01(I_arr),
        "S":            norm01(S_arr),
        "demand":       norm01(rolling_mean),
        "alert_rate":   rate,
        "alert_count":  counts.astype(float),
        "survey_gap":   survey_mask,
    })
    return df


_PROXY_SPEC_TRANSIENT = {
    "dataset_id":    "cosmo_transient_synth",
    "sector":        "cosmo",
    "pilot":         "transient",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "perturbation_column": "survey_gap",
    "perturbation_type":   "symbolic_cut",
    "perturbation_note":   "survey_gap=1 marks planned survey downtime (standard instrument test).",
    "columns": [
        {
            "oric_role": "O", "source_column": "O", "direction": "positive",
            "fragility_score": 0.40,
            "fragility_note": "Survey cadence must be uniform; scheduling gaps distort regularity",
            "manipulability_note": "Not manipulable for a fixed survey schedule",
            "description": "Survey rate regularity (inverse of rolling rate CV)",
        },
        {
            "oric_role": "R", "source_column": "R", "direction": "positive",
            "fragility_score": 0.35,
            "fragility_note": "Baseline rate must be estimated pre-burst (pre-registered)",
            "manipulability_note": "Baseline window is a pre-registered parameter",
            "description": "Rate return to baseline after burst (resilience)",
        },
        {
            "oric_role": "I", "source_column": "I", "direction": "positive",
            "fragility_score": 0.50,
            "fragility_note": "Multi-band splitting is synthetic; real data requires filter mapping",
            "manipulability_note": "Correlation window size is pre-registered",
            "description": "Multi-band count correlation (integration/coherence)",
        },
        {
            "oric_role": "S", "source_column": "S", "direction": "positive",
            "fragility_score": 0.35,
            "fragility_note": "Burst threshold must be pre-specified",
            "manipulability_note": "Threshold change requires new pre-registration",
            "description": "Cumulative transient signal above baseline (symbolic stock)",
        },
        {
            "oric_role": "demand", "source_column": "demand", "direction": "positive",
            "fragility_score": 0.30,
            "fragility_note": "Rolling alert rate depends on cadence and detection sensitivity",
            "manipulability_note": "Detection efficiency changes are a known confound",
            "description": "Rolling mean alert rate (environmental demand on detection system)",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Dispatch and CLI
# --------------------------------------------------------------------------- #

_PILOTS = {
    "solar":     (_generate_solar,     _PROXY_SPEC_SOLAR),
    "stellar":   (_generate_stellar,   _PROXY_SPEC_STELLAR),
    "transient": (_generate_transient, _PROXY_SPEC_TRANSIENT),
}


def generate(outdir: Path, seed: int, pilot_id: str, n: int = 300) -> None:
    """Public entry point called by sector_panel_runner."""
    outdir.mkdir(parents=True, exist_ok=True)
    if pilot_id not in _PILOTS:
        raise ValueError(f"Unknown pilot: '{pilot_id}'. Choose from {list(_PILOTS)}")
    gen_fn, spec = _PILOTS[pilot_id]
    df = gen_fn(n, seed)
    df.to_csv(outdir / "real.csv", index=False)
    with open(outdir / "proxy_spec.json", "w") as f:
        json.dump(spec, f, indent=2)
    print(f"[cosmo/generate_synth] pilot={pilot_id} → {outdir}  ({len(df)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cosmo sector synthetic data")
    parser.add_argument("--pilot",  choices=list(_PILOTS), default="solar")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed",   type=int, default=42)
    parser.add_argument("--n",      type=int, default=300)
    args = parser.parse_args()
    generate(Path(args.outdir), args.seed, args.pilot, args.n)


if __name__ == "__main__":
    main()
main
