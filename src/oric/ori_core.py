from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple
import numpy as np
import pandas as pd


def compute_cap_projection(O: pd.Series, R: pd.Series, I: pd.Series, form: str = "product") -> pd.Series:
    """Compute Cap(t) from O, R, I using a fixed ex ante projection.

    Supported forms:
    - product: Cap = O * R * I
    - geom_mean: Cap = (O * R * I) ** (1/3)
    - weighted_sum: Cap = 0.4*O + 0.35*R + 0.25*I
    """
    if form == "product":
        return O * R * I
    if form == "geom_mean":
        return (O * R * I) ** (1.0 / 3.0)
    if form == "weighted_sum":
        return 0.4 * O + 0.35 * R + 0.25 * I
    raise ValueError(f"Unknown cap form: {form}")


def compute_sigma(demand: pd.Series, cap: pd.Series, form: str = "relu_diff") -> pd.Series:
    """Compute mismatch Sigma(t) = max(0, demand - cap)."""
    if form != "relu_diff":
        raise ValueError(f"Unknown sigma form: {form}")
    return np.maximum(0.0, demand - cap)


def compute_viability(df: pd.DataFrame, omega: Tuple[float, float, float, float]) -> pd.Series:
    """Compute V(t) as a weighted mean of survivability components."""
    cols = ["survie", "energie_nette", "integrite", "persistance"]
    for c in cols:
        if c not in df.columns:
            raise KeyError(f"Missing column: {c}")
    w = np.array(omega, dtype=float)
    w = w / w.sum()
    return (w[0] * df[cols[0]] + w[1] * df[cols[1]] + w[2] * df[cols[2]] + w[3] * df[cols[3]])


def summarize_run(df: pd.DataFrame, window_W: int = 20) -> Dict[str, float]:
    """Summarize a single run time series into decision metrics."""
    if "Sigma" not in df.columns or "V" not in df.columns:
        raise KeyError("df must include Sigma and V columns")

    if len(df) < window_W:
        window_W = max(1, len(df))

    tail = df.iloc[-window_W:]
    v_q05 = float(np.quantile(tail["V"].to_numpy(), 0.05))
    a_sigma = float(df["Sigma"].sum())
    frac_over = float((df["Sigma"] > 0).mean())
    return {
        "V_q05": v_q05,
        "A_sigma": a_sigma,
        "frac_over": frac_over,
    }
