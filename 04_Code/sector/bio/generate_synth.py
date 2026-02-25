#!/usr/bin/env python3
"""04_Code/sector/bio/generate_synth.py

Synthetic time series for the biology sector pilots.

Pilots: epidemic, geneexpr, ecology

Design constraints (checked by sector_panel_runner.mapping_validity_check):
- O, R, I are mean-reverting AR(1) processes → ADF p < 0.1
- |corr(O,R)|, |corr(O,I)|, |corr(R,I)| < 0.7 (independent noise sources)
- A demand shock mid-series drives Sigma > 0, triggering S accumulation and C transition
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ── Per-pilot AR(1) parameters ──────────────────────────────────────────────────
#
# Each proxy uses an independent noise source. phi controls persistence (< 1 for
# stationarity). Means and standard deviations are chosen so that pairwise
# correlations remain well below 0.7.
#
# phi     : AR(1) coefficient (persistence). Higher = slower series.
# mu      : Long-run mean in [0,1].
# sigma   : Innovation standard deviation.
# demand_base_ratio : demand / Cap ratio during baseline (no stress).
# shock_factor      : demand multiplier during mid-series shock.
# shock_start_frac  : fraction of n_steps at which shock starts.
# shock_end_frac    : fraction of n_steps at which shock ends.

_PILOT_CONFIGS: dict[str, dict] = {
    "epidemic": {
        "O": {"phi": 0.82, "mu": 0.50, "sigma": 0.035},   # hospitalization burden rate
        "R": {"phi": 0.88, "mu": 0.63, "sigma": 0.020},   # vaccine / immunity coverage
        "I": {"phi": 0.58, "mu": 0.55, "sigma": 0.050},   # care-coordination efficiency
        "demand_base_ratio": 0.82,
        "shock_factor": 1.28,
        "shock_start_frac": 0.30,
        "shock_end_frac": 0.65,
    },
    "geneexpr": {
        "O": {"phi": 0.72, "mu": 0.52, "sigma": 0.040},   # mean expression level
        "R": {"phi": 0.90, "mu": 0.66, "sigma": 0.015},   # epigenetic buffering capacity
        "I": {"phi": 0.62, "mu": 0.58, "sigma": 0.045},   # cross-pathway integration
        "demand_base_ratio": 0.84,
        "shock_factor": 1.22,
        "shock_start_frac": 0.33,
        "shock_end_frac": 0.60,
    },
    "ecology": {
        "O": {"phi": 0.85, "mu": 0.62, "sigma": 0.028},   # species-richness index
        "R": {"phi": 0.93, "mu": 0.57, "sigma": 0.012},   # habitat quality
        "I": {"phi": 0.67, "mu": 0.54, "sigma": 0.042},   # dispersal network connectivity
        "demand_base_ratio": 0.80,
        "shock_factor": 1.30,
        "shock_start_frac": 0.28,
        "shock_end_frac": 0.62,
    },
}


def generate(pilot_id: str, seed: int, n_steps: int) -> pd.DataFrame:
    """Generate a synthetic panel for the given bio pilot.

    Returns a DataFrame with columns: t, O, R, I, demand.
    O, R, I are stationary AR(1) series in [0,1] with low pairwise correlation.
    """
    if pilot_id not in _PILOT_CONFIGS:
        raise ValueError(f"Unknown bio pilot: {pilot_id!r}. Choose from {sorted(_PILOT_CONFIGS)}")

    cfg = _PILOT_CONFIGS[pilot_id]
    rng = np.random.default_rng(int(seed))

    t = np.arange(int(n_steps), dtype=int)
    cap_scale = 1_000.0

    # Generate O, R, I as independent AR(1) processes
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

    # Demand shock: mid-series pressure surge
    shock_start = int(cfg["shock_start_frac"] * n_steps)
    shock_end = int(cfg["shock_end_frac"] * n_steps)
    shock_mask = (t >= shock_start) & (t < shock_end)

    demand_noise = rng.normal(0.0, 0.02 * base_demand.mean(), size=int(n_steps))
    demand = base_demand + demand_noise
    demand[shock_mask] *= float(cfg["shock_factor"])

    return pd.DataFrame({"t": t, "O": O, "R": R, "I": I, "demand": demand})
