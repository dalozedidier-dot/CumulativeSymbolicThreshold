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
