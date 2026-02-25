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
