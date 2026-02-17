from __future__ import annotations

from typing import Dict, Tuple, Optional
import numpy as np
import pandas as pd


def compute_stock_S(df: pd.DataFrame, alpha_s: Tuple[float, float, float, float]) -> pd.Series:
    cols = ["repertoire", "codification", "densite_transmission", "fidelite"]
    for c in cols:
        if c not in df.columns:
            raise KeyError(f"Missing column: {c}")
    w = np.array(alpha_s, dtype=float)
    w = w / w.sum()
    return (w[0] * df[cols[0]] + w[1] * df[cols[1]] + w[2] * df[cols[2]] + w[3] * df[cols[3]])


def compute_order_C(df: pd.DataFrame) -> pd.Series:
    """Simplified order variable C(t).

    Default rule:
    - delta_S = S(t) - S(t-1)
    - delta_V = V(t) - V(t-1)
    - C(t) accumulates delta_V only when delta_S > 0 and delta_V > 0
    """
    if "S" not in df.columns or "V" not in df.columns:
        raise KeyError("df must include S and V columns")
    delta_s = df["S"].diff().fillna(0.0)
    delta_v = df["V"].diff().fillna(0.0)
    gain = np.where((delta_s > 0) & (delta_v > 0), delta_v, 0.0)
    return pd.Series(np.cumsum(gain), index=df.index, name="C")


def detect_s_star_piecewise(S: np.ndarray, C: np.ndarray) -> Dict[str, float]:
    """Detect a piecewise threshold S* using a simple grid search.

    Returns best S_star and improvement score (SSE reduction ratio).
    This is a diagnostic helper, not a decision rule unless preregistered.
    """
    S = np.asarray(S, dtype=float)
    C = np.asarray(C, dtype=float)
    if len(S) < 10:
        return {"S_star": float("nan"), "improvement": 0.0}

    # Candidate split points between 20% and 80%
    idxs = range(int(0.2 * len(S)), int(0.8 * len(S)))
    best = (None, -np.inf)
    for i in idxs:
        s_star = S[i]
        left = S <= s_star
        right = ~left
        if left.sum() < 3 or right.sum() < 3:
            continue

        # Fit two means
        mu1 = C[left].mean()
        mu2 = C[right].mean()
        sse_piece = ((C[left] - mu1) ** 2).sum() + ((C[right] - mu2) ** 2).sum()

        mu = C.mean()
        sse_one = ((C - mu) ** 2).sum()
        improvement = 1.0 - (sse_piece / sse_one if sse_one > 0 else 1.0)
        if improvement > best[1]:
            best = (float(s_star), float(improvement))

    if best[0] is None:
        return {"S_star": float("nan"), "improvement": 0.0}
    return {"S_star": best[0], "improvement": best[1]}
