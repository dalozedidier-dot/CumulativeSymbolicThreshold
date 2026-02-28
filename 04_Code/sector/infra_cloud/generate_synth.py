"""generate_synth.py — Minimal synthetic generator for the sector.

This is intentionally lightweight. It exists so the sector suite can run
synthetic demos if needed, but the preferred validation path is real data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate(pilot_id: str, n: int = 2000, seed: int = 1234) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)

    # Base signal with a regime shift
    base = 0.02 * t + 0.5 * np.sin(t / 30.0)
    shift = (t > n * 0.6).astype(float) * 2.0
    x = base + shift + rng.normal(0, 0.2, size=n)

    # ORI-C style derived columns
    O = x
    dev = x - pd.Series(x).rolling(200, min_periods=1).median().to_numpy()
    R = -np.diff(dev, prepend=dev[0])
    I = pd.Series(np.abs(np.diff(dev, prepend=dev[0]))).rolling(50, min_periods=1).median().to_numpy()
    demand = O
    S = np.cumsum(np.maximum(dev, 0.0))

    return pd.DataFrame({"t": t, "O": O, "R": R, "I": I, "demand": demand, "S": S})
