#!/usr/bin/env python3
"""04_Code/sector/infra/generate_synth.py

Synthetic time series for the infrastructure sector pilots.

Pilots: grid, traffic, finance

Design constraints: stationary AR(1) proxies, low pairwise collinearity,
mid-series demand shock to trigger C transition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_PILOT_CONFIGS: dict[str, dict] = {
    "grid": {
        # Electrical grid reliability system
        "O": {"phi": 0.83, "mu": 0.60, "sigma": 0.030},   # grid load factor
        "R": {"phi": 0.90, "mu": 0.65, "sigma": 0.015},   # redundancy / reserve margin
        "I": {"phi": 0.62, "mu": 0.53, "sigma": 0.044},   # inter-region coordination
        "demand_base_ratio": 0.84,
        "shock_factor": 1.26,
        "shock_start_frac": 0.30,
        "shock_end_frac": 0.62,
    },
    "traffic": {
        # Urban traffic / mobility network
        "O": {"phi": 0.76, "mu": 0.55, "sigma": 0.038},   # network utilization rate
        "R": {"phi": 0.88, "mu": 0.62, "sigma": 0.018},   # route redundancy index
        "I": {"phi": 0.58, "mu": 0.56, "sigma": 0.050},   # multi-modal integration
        "demand_base_ratio": 0.82,
        "shock_factor": 1.29,
        "shock_start_frac": 0.32,
        "shock_end_frac": 0.64,
    },
    "finance": {
        # Financial market infrastructure
        "O": {"phi": 0.79, "mu": 0.57, "sigma": 0.035},   # clearing system throughput
        "R": {"phi": 0.91, "mu": 0.63, "sigma": 0.014},   # systemic risk buffer
        "I": {"phi": 0.64, "mu": 0.54, "sigma": 0.043},   # cross-market integration
        "demand_base_ratio": 0.83,
        "shock_factor": 1.24,
        "shock_start_frac": 0.31,
        "shock_end_frac": 0.61,
    },
}


def generate(pilot_id: str, seed: int, n_steps: int) -> pd.DataFrame:
    """Generate a synthetic panel for the given infra pilot."""
    if pilot_id not in _PILOT_CONFIGS:
        raise ValueError(f"Unknown infra pilot: {pilot_id!r}. Choose from {sorted(_PILOT_CONFIGS)}")

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
"""generate_synth.py — Synthetic data generator for the Infra sector panel.

Three pilots:

  grid    : Electrical grid — frequency deviation, reserve margin, cross-border flows
            Regime transition: normal operation → demand surge → capacity stress → NPC event
            Perturbation: sudden load shock (generator trip / heat wave demand spike)

  traffic : Urban traffic network — congestion ratio, resilience index, flow coherence
            Regime change: free-flow → congested → gridlock
            Perturbation: incident or road closure (symbolic cut of routing information)

  finance : Macro-financial regime — volatility, credit spread, liquidity index
            Regime change: low-volatility regime → crisis onset
            Perturbation: policy intervention (rate hike, QE announcement)

ORI-C fits naturally here: these systems have organisation, resilience, and integration
that can be probed by controlled or quasi-experimental perturbations.

The finance pilot reuses the sector structure but with financial proxies;
it is methodologically equivalent to the FRED monthly pilot in the canonical suite,
extended with explicit shock annotation (U(t) column).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Electrical grid
# --------------------------------------------------------------------------- #

def _generate_grid(n: int, seed: int) -> pd.DataFrame:
    """Simulate grid frequency stability, reserve margin, cross-border flows."""
    rng = np.random.default_rng(seed)
    t_arr = np.arange(n)

    # Base demand: sinusoidal daily/weekly pattern + trend
    daily    = np.sin(2 * np.pi * t_arr / 24)
    weekly   = 0.3 * np.sin(2 * np.pi * t_arr / (24 * 7))
    trend    = 0.001 * t_arr / n
    demand_base = 0.6 + 0.2 * daily + 0.1 * weekly + trend
    demand_base = np.clip(demand_base + rng.normal(0, 0.02, n), 0, 1)

    # Shock event at n//2: sudden load surge (heat wave / cold snap)
    shock_t   = n // 2
    shock_dur = n // 8
    shock_amp = 0.25
    shock_profile = np.zeros(n)
    shock_profile[shock_t:shock_t+shock_dur] = (
        shock_amp * np.exp(-np.arange(shock_dur) / (shock_dur / 3))
    )
    demand = np.clip(demand_base + shock_profile, 0, 1)

    # Reserve margin (resilience): drops during shock
    reserve = np.zeros(n)
    reserve[0] = 0.75
    for t in range(1, n):
        stress     = max(demand[t] - 0.75, 0)
        recovery   = 0.01 * (0.75 - reserve[t-1])
        reserve[t] = np.clip(reserve[t-1] - 0.08 * stress + recovery + rng.normal(0, 0.01), 0, 1)

    # Frequency deviation (organisation): 50 Hz nominal; deviation proxy
    freq_dev = np.zeros(n)
    for t in range(1, n):
        # Load-generation imbalance drives frequency deviation
        imbalance = demand[t] - (reserve[t] + 0.25)
        freq_dev[t] = np.clip(abs(imbalance) + rng.normal(0, 0.02), 0, 1)
    O_arr = 1.0 - freq_dev   # high O = stable frequency

    # Cross-border flow coherence (integration): coupling between zones
    I_arr = np.zeros(n)
    W = 12
    zone_a = demand + rng.normal(0, 0.03, n)
    zone_b = demand * 0.8 + rng.normal(0, 0.05, n)
    for t in range(W, n):
        c = np.corrcoef(zone_a[t-W:t], zone_b[t-W:t])[0, 1]
        I_arr[t] = abs(c) if np.isfinite(c) else 0.0
    I_arr[:W] = I_arr[W]

    # Demand response cumulation (symbolic stock): memory of smart-grid interventions
    S_arr = np.zeros(n)
    DR_THRESH = 0.80   # demand response activates above this load
    for t in range(1, n):
        dr_event  = max(demand[t] - DR_THRESH, 0) * 0.2
        decay     = 0.004 * S_arr[t-1]
        S_arr[t]  = np.clip(S_arr[t-1] + dr_event - decay + rng.normal(0, 0.003), 0, 1)

    # Shock annotation column
    U_arr = shock_profile.copy()

    def norm01(x):
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":             t_arr,
        "O":             norm01(O_arr),
        "R":             norm01(reserve),
        "I":             norm01(I_arr),
        "S":             norm01(S_arr),
        "demand":        norm01(demand),
        "U":             U_arr,          # exogenous shock (annotated U(t))
        "freq_dev_raw":  freq_dev,
        "reserve_raw":   reserve,
        "demand_raw":    demand,
    })
    return df


_PROXY_SPEC_GRID = {
    "dataset_id":    "infra_grid_synth",
    "sector":        "infra",
    "pilot":         "grid",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "perturbation_column": "U",
    "perturbation_type":   "demand_shock",
    "perturbation_note":   "U > 0 marks a sudden demand surge (heat wave / generator trip).",
    "columns": [
        {
            "oric_role": "O", "source_column": "O", "direction": "positive",
            "fragility_score": 0.30,
            "fragility_note": "Frequency deviation proxy requires sub-second resolution in real data",
            "manipulability_note": "Grid operators can mask small deviations through re-dispatch",
            "description": "1 − frequency_deviation: grid frequency stability (organisation)",
        },
        {
            "oric_role": "R", "source_column": "R", "direction": "positive",
            "fragility_score": 0.35,
            "fragility_note": "Reserve margin definition varies by TSO methodology",
            "manipulability_note": "TSOs can declare capacity as unavailable; reported reserve may underestimate real buffer",
            "description": "Reserve margin: spare generation capacity / peak demand (resilience)",
        },
        {
            "oric_role": "I", "source_column": "I", "direction": "positive",
            "fragility_score": 0.45,
            "fragility_note": "Cross-border flow data must be synchronised across TSOs",
            "manipulability_note": "Congestion management can alter apparent flow patterns",
            "description": "Cross-border flow coherence between zones (integration)",
        },
        {
            "oric_role": "S", "source_column": "S", "direction": "positive",
            "fragility_score": 0.40,
            "fragility_note": "Demand response participation rates are partially confidential",
            "manipulability_note": "DR activation thresholds are operator-specific",
            "description": "Cumulative demand response participation (symbolic stock)",
        },
        {
            "oric_role": "demand", "source_column": "demand", "direction": "positive",
            "fragility_score": 0.20,
            "fragility_note": "Load forecast is typically accurate ±2%; real-time data preferred",
            "manipulability_note": "Demand can be shaped by DSM programmes (known confound)",
            "description": "Total electricity demand (normalised) — environmental demand on grid",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Traffic
# --------------------------------------------------------------------------- #

def _generate_traffic(n: int, seed: int) -> pd.DataFrame:
    """Simulate urban traffic: free-flow → congested → gridlock."""
    rng = np.random.default_rng(seed)
    t_arr = np.arange(n)

    # Rush-hour pattern + incident
    hour = t_arr % 24
    base_load = 0.3 + 0.5 * np.exp(-((hour - 8)**2) / 8) + 0.4 * np.exp(-((hour - 17.5)**2) / 6)
    base_load = np.clip(base_load + rng.normal(0, 0.03, n), 0, 1)

    # Incident at n//2: road closure → gridlock cascade
    incident_t   = n // 2
    incident_dur = n // 6
    incident     = np.zeros(n)
    incident[incident_t:incident_t+incident_dur] = np.linspace(0, 0.5, incident_dur)

    total_load = np.clip(base_load + incident, 0, 1)

    # Speed ratio (Organisation): free-speed / current speed
    # BPR (Bureau of Public Roads) function: speed degrades with load^4
    speed_ratio = 1.0 / (1.0 + 0.15 * total_load**4)
    O_arr = speed_ratio

    # Resilience: how quickly speed recovers after incident
    R_arr = np.zeros(n)
    R_arr[0] = 0.9
    for t in range(1, n):
        drop = 0.15 * incident[t]
        recovery = 0.03 * (0.9 - R_arr[t-1]) * (1 - incident[t])
        R_arr[t] = np.clip(R_arr[t-1] - drop + recovery + rng.normal(0, 0.01), 0, 1)

    # Integration: network coherence — correlation between parallel routes
    route_a = total_load + rng.normal(0, 0.04, n)
    route_b = total_load * 0.85 + 0.1 + rng.normal(0, 0.06, n)
    I_arr = np.zeros(n)
    W = 12
    for t in range(W, n):
        c = np.corrcoef(route_a[t-W:t], route_b[t-W:t])[0, 1]
        I_arr[t] = abs(c) if np.isfinite(c) else 0.0
    I_arr[:W] = I_arr[W]

    # Symbolic stock: routing information memory (GPS/adaptive routing)
    # Decreases when incident disrupts real-time routing updates
    S_arr = np.zeros(n)
    S_arr[0] = 0.7
    for t in range(1, n):
        gain  = 0.01 * (1 - incident[t]) * speed_ratio[t]
        loss  = 0.02 * incident[t]
        decay = 0.003 * S_arr[t-1]
        S_arr[t] = np.clip(S_arr[t-1] + gain - loss - decay + rng.normal(0, 0.005), 0, 1)

    def norm01(x):
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":          t_arr,
        "O":          norm01(O_arr),
        "R":          norm01(R_arr),
        "I":          norm01(I_arr),
        "S":          norm01(S_arr),
        "demand":     norm01(total_load),
        "U":          incident,
        "speed_ratio_raw": speed_ratio,
        "load_raw":        total_load,
    })
    return df


_PROXY_SPEC_TRAFFIC = {
    "dataset_id":    "infra_traffic_synth",
    "sector":        "infra",
    "pilot":         "traffic",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "perturbation_column": "U",
    "perturbation_type":   "capacity_hit",
    "perturbation_note":   "U > 0 marks an incident / road closure (capacity reduction shock).",
    "columns": [
        {
            "oric_role": "O", "source_column": "O", "direction": "positive",
            "fragility_score": 0.30, "fragility_note": "BPR parameters vary by road type",
            "manipulability_note": "Speed data can be spoofed by navigation apps",
            "description": "Speed ratio (free-speed / current speed): traffic organisation",
        },
        {
            "oric_role": "R", "source_column": "R", "direction": "positive",
            "fragility_score": 0.35, "fragility_note": "Recovery rate depends on incident clearance time",
            "manipulability_note": "Emergency response protocols affect recovery",
            "description": "Speed recovery after incident (resilience)",
        },
        {
            "oric_role": "I", "source_column": "I", "direction": "positive",
            "fragility_score": 0.45, "fragility_note": "Parallel route correlation is network-topology-dependent",
            "manipulability_note": "Real-time re-routing changes apparent correlation",
            "description": "Parallel route correlation (network integration)",
        },
        {
            "oric_role": "S", "source_column": "S", "direction": "positive",
            "fragility_score": 0.55, "fragility_note": "Routing memory depends on algorithm and update frequency",
            "manipulability_note": "Commercial navigation providers change algorithms opaquely",
            "description": "Adaptive routing memory / GPS signal density (symbolic stock)",
        },
        {
            "oric_role": "demand", "source_column": "demand", "direction": "positive",
            "fragility_score": 0.25, "fragility_note": "Load proxy depends on loop detectors or FCD",
            "manipulability_note": "Traffic management can shift demand temporally",
            "description": "Total network load (normalised) — environmental demand",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Finance macro
# --------------------------------------------------------------------------- #

def _generate_finance(n: int, seed: int) -> pd.DataFrame:
    """Simulate macro-financial regime: low-vol → crisis → intervention."""
    rng = np.random.default_rng(seed)
    t_arr = np.arange(n)

    # Volatility (GARCH-like)
    vol = np.zeros(n)
    vol[0] = 0.01
    crisis_t = n // 3
    vol_shock = n // 2
    interv_t  = 2 * n // 3

    for t in range(1, n):
        shock = 0.0
        if t == vol_shock:
            shock = 0.08
        mean_revert = 0.01 * (0.01 - vol[t-1])
        vol[t] = np.clip(0.9 * vol[t-1] + shock + mean_revert + rng.normal(0, 0.002), 0.001, 0.2)

    # Credit spread (demand proxy)
    spread = 0.01 + 5 * vol + rng.normal(0, 0.002, n)
    spread = np.clip(spread, 0, 1)

    # Liquidity index (R proxy): degrades during crisis
    liquidity = np.zeros(n)
    liquidity[0] = 0.85
    for t in range(1, n):
        stress    = max(spread[t] - 0.05, 0) * 2
        recovery  = 0.02 * (0.85 - liquidity[t-1]) * (1 if t >= interv_t else 0)
        liquidity[t] = np.clip(liquidity[t-1] - stress + recovery + rng.normal(0, 0.01), 0, 1)

    # Organisation: inverse volatility regime stability
    O_arr = 1.0 / (1.0 + 10 * vol)

    # Integration: cross-asset correlation (stocks + bonds)
    asset_a = -vol * 5 + rng.normal(0, 0.02, n)   # equity returns
    asset_b = vol * 3 + rng.normal(0, 0.02, n)    # flight-to-quality bonds
    I_arr = np.zeros(n)
    W = 15
    for t in range(W, n):
        c = np.corrcoef(asset_a[t-W:t], asset_b[t-W:t])[0, 1]
        I_arr[t] = abs(c) if np.isfinite(c) else 0.0
    I_arr[:W] = I_arr[W]

    # Symbolic stock: accumulated policy credibility / forward guidance
    S_arr = np.zeros(n)
    S_arr[0] = 0.6
    for t in range(1, n):
        policy_boost = 0.03 if t >= interv_t else 0.0
        erosion = 0.008 * max(spread[t] - 0.05, 0)
        decay   = 0.002 * S_arr[t-1]
        S_arr[t] = np.clip(S_arr[t-1] + policy_boost - erosion - decay + rng.normal(0, 0.004), 0, 1)

    # U(t): intervention (rate hike / QE announcement)
    U_arr = np.zeros(n)
    U_arr[interv_t] = 1.0

    def norm01(x):
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":           t_arr,
        "O":           norm01(O_arr),
        "R":           norm01(liquidity),
        "I":           norm01(I_arr),
        "S":           norm01(S_arr),
        "demand":      norm01(spread),
        "U":           U_arr,
        "vol_raw":     vol,
        "spread_raw":  spread,
    })
    return df


_PROXY_SPEC_FINANCE = {
    "dataset_id":    "infra_finance_synth",
    "sector":        "infra",
    "pilot":         "finance",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "perturbation_column": "U",
    "perturbation_type":   "exogenous_intervention",
    "perturbation_note":   "U=1 marks a policy intervention (rate decision / QE announcement).",
    "columns": [
        {
            "oric_role": "O", "source_column": "O", "direction": "positive",
            "fragility_score": 0.40, "fragility_note": "Volatility regime depends on asset universe and frequency",
            "manipulability_note": "Implied vol can be influenced by options market positioning",
            "description": "1 / (1 + 10·vol): inverse volatility (financial organisation)",
        },
        {
            "oric_role": "R", "source_column": "R", "direction": "positive",
            "fragility_score": 0.45, "fragility_note": "Liquidity indices vary by provider (bid-ask, depth)",
            "manipulability_note": "Central bank liquidity operations directly affect this proxy",
            "description": "Liquidity index: bid-ask spread based (system resilience)",
        },
        {
            "oric_role": "I", "source_column": "I", "direction": "positive",
            "fragility_score": 0.55, "fragility_note": "Cross-asset correlation is regime-switching by construction",
            "manipulability_note": "ETF flows can alter apparent correlation structurally",
            "description": "Equity-bond return correlation (financial integration/coherence)",
        },
        {
            "oric_role": "S", "source_column": "S", "direction": "positive",
            "fragility_score": 0.65, "fragility_note": "Policy credibility is inherently difficult to operationalise",
            "manipulability_note": "High: central bank communication directly affects this proxy",
            "description": "Accumulated policy credibility / forward guidance (symbolic stock)",
        },
        {
            "oric_role": "demand", "source_column": "demand", "direction": "positive",
            "fragility_score": 0.35, "fragility_note": "Credit spreads depend on issuer universe",
            "manipulability_note": "ECB/Fed purchase programmes compress spreads directly",
            "description": "Credit spread (investment-grade) — stress demand on financial system",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Dispatch and CLI
# --------------------------------------------------------------------------- #

_PILOTS = {
    "grid":    (_generate_grid,    _PROXY_SPEC_GRID),
    "traffic": (_generate_traffic, _PROXY_SPEC_TRAFFIC),
    "finance": (_generate_finance, _PROXY_SPEC_FINANCE),
}


def generate(outdir: Path, seed: int, pilot_id: str, n: int = 300) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    if pilot_id not in _PILOTS:
        raise ValueError(f"Unknown pilot: '{pilot_id}'. Choose from {list(_PILOTS)}")
    gen_fn, spec = _PILOTS[pilot_id]
    df = gen_fn(n, seed)
    df.to_csv(outdir / "real.csv", index=False)
    with open(outdir / "proxy_spec.json", "w") as f:
        json.dump(spec, f, indent=2)
    print(f"[infra/generate_synth] pilot={pilot_id} → {outdir}  ({len(df)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate infra sector synthetic data")
    parser.add_argument("--pilot",  choices=list(_PILOTS), default="grid")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed",   type=int, default=42)
    parser.add_argument("--n",      type=int, default=300)
    args = parser.parse_args()
    generate(Path(args.outdir), args.seed, args.pilot, args.n)


if __name__ == "__main__":
    main()
main
