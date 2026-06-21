"""multiverse.py — Specification-curve / multiverse robustness for ORI-C.

Why this exists
---------------
The framework's `mapping_validity` lock treats any proxy change as invalidating a
comparison — excellent against p-hacking, but insufficient for *confirmation*. A
genuine signature must survive **several equally defensible** analytic choices. If
an ACCEPT holds only for one proxy/normalisation and collapses for another
reasonable one, that is fragility, not evidence (the "garden of forking paths").

This module runs ORI-C across a pre-declared grid of defensible specifications
and reports the **whole distribution** of verdicts, not a single hand-picked
choice. The forking axes are deliberately orthogonal and analytic (they do not
touch the frozen detector parameters k, m, baseline_n):

  - ``normalize``            : {robust_minmax, zscore, minmax}   (scaling choice)
  - ``smooth``               : {none, ma3, ma5}                  (denoising window)
  - ``demand_to_cap_ratio``  : {0.85, 0.90, 0.95}                (auto-scale target)

→ 27 specifications. For each we run the *real* detector path and record whether
the sustained crossing fires and its crossing rate.

Robustness verdict (frozen ex ante; see 02_Protocol addendum, Test C):
  - ROBUST_POSITIVE  : fired_fraction ≥ 0.80
  - ROBUST_NEGATIVE  : fired_fraction ≤ 0.20
  - FRAGILE          : otherwise — the verdict depends on arbitrary proxy choices
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import product
from typing import Callable, Sequence

import numpy as np
import pandas as pd

NORMALIZE_CHOICES = ("robust_minmax", "zscore", "minmax")
SMOOTH_CHOICES = ("none", "ma3", "ma5")
DEMAND_RATIO_CHOICES = (0.85, 0.90, 0.95)

ROBUST_FRACTION = 0.80  # frozen: ≥ this share of specs must agree for "robust"

_PROXY_COLS = ("O", "R", "I", "demand")


# ---------------------------------------------------------------------------
# Specification grid
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Specification:
    normalize: str
    smooth: str
    demand_to_cap_ratio: float

    @property
    def label(self) -> str:
        return f"{self.normalize}|{self.smooth}|r{self.demand_to_cap_ratio}"

    def to_dict(self) -> dict:
        return asdict(self)


def specification_grid(
    normalize: Sequence[str] = NORMALIZE_CHOICES,
    smooth: Sequence[str] = SMOOTH_CHOICES,
    demand_ratios: Sequence[float] = DEMAND_RATIO_CHOICES,
) -> list[Specification]:
    """Full Cartesian grid of defensible specifications."""
    return [Specification(n, s, float(r)) for n, s, r in product(normalize, smooth, demand_ratios)]


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def _smooth(arr: np.ndarray, kind: str) -> np.ndarray:
    if kind == "none":
        return arr
    w = {"ma3": 3, "ma5": 5}[kind]
    s = pd.Series(arr).rolling(window=w, min_periods=1, center=True).mean()
    return np.asarray(s.to_numpy(), dtype=float)


def _normalize(arr: np.ndarray, method: str) -> np.ndarray:
    a = np.asarray(arr, dtype=float)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        empty: np.ndarray = np.clip(np.nan_to_num(a, nan=0.5), 0.02, 0.98)
        return empty
    if method == "zscore":
        mu, sd = float(np.mean(finite)), float(np.std(finite))
        if sd > 1e-10:
            a = (a - mu) / sd
    if method == "robust_minmax":
        lo, hi = np.percentile(finite, 2), np.percentile(finite, 98)
    else:  # minmax and (post-zscore) minmax mapping
        lo, hi = float(np.min(a[np.isfinite(a)])), float(np.max(a[np.isfinite(a)]))
    if hi <= lo:
        degenerate: np.ndarray = np.clip(np.nan_to_num(a, nan=0.5), 0.02, 0.98)
        return degenerate
    scaled: np.ndarray = np.clip((a - lo) / (hi - lo) * 0.80 + 0.10, 0.02, 0.98)
    return scaled


def apply_specification(df: pd.DataFrame, spec: Specification) -> pd.DataFrame:
    """Return a copy of ``df`` with the spec's smoothing + normalisation applied
    to the ORI-C proxy columns (O, R, I, demand). ``t`` and any other columns are
    preserved; ``demand`` is normalised too so the auto-scale target is comparable."""
    out = df.copy()
    for col in _PROXY_COLS:
        if col not in out.columns:
            continue
        vals = pd.to_numeric(out[col], errors="coerce").to_numpy(dtype=float)
        out[col] = _normalize(_smooth(vals, spec.smooth), spec.normalize)
    return out


# ---------------------------------------------------------------------------
# Multiverse runner
# ---------------------------------------------------------------------------

@dataclass
class SpecOutcome:
    spec: dict
    detector_fired: bool
    crossing_rate: float
    max_run: int

    def to_dict(self) -> dict:
        return {"spec": self.spec, "detector_fired": self.detector_fired,
                "crossing_rate": round(self.crossing_rate, 6), "max_run": self.max_run}


def run_multiverse(
    df_obs: pd.DataFrame,
    cfg,
    *,
    specs: Sequence[Specification] | None = None,
    run_fn: Callable | None = None,
) -> dict:
    """Run ORI-C across the specification grid and summarise the verdict spread.

    Returns a dict with per-spec outcomes plus:
      - ``fired_fraction``        : share of specs with a sustained crossing
      - ``crossing_rate_quartiles``: distribution of the crossing rate
      - ``robustness``            : ROBUST_POSITIVE / ROBUST_NEGATIVE / FRAGILE
    """
    from oric.surrogates import threshold_crossing_statistic  # local
    if run_fn is None:
        try:
            from pipeline.ori_c_pipeline import run_oric_from_observations  # type: ignore
        except ModuleNotFoundError:  # pragma: no cover - layout-dependent
            from ori_c_pipeline import run_oric_from_observations  # type: ignore
        run_fn = run_oric_from_observations

    if specs is None:
        specs = specification_grid()

    k = float(getattr(cfg, "k", 2.5))
    m = int(getattr(cfg, "m", 3))
    baseline_n = int(getattr(cfg, "baseline_n", 30))

    outcomes: list[SpecOutcome] = []
    for spec in specs:
        d = apply_specification(df_obs, spec)
        out = run_fn(d, cfg, demand_to_cap_ratio=spec.demand_to_cap_ratio)
        if "delta_C" not in out.columns:
            out = out.copy()
            out["delta_C"] = out["C"].diff().fillna(0.0)
        cs = threshold_crossing_statistic(out["delta_C"].to_numpy(), k=k, m=m, baseline_n=baseline_n)
        outcomes.append(SpecOutcome(spec.to_dict(), cs.sustained_hit, cs.crossing_rate, cs.max_run))

    fired = np.array([o.detector_fired for o in outcomes], dtype=bool)
    rates = np.array([o.crossing_rate for o in outcomes], dtype=float)
    fired_fraction = float(fired.mean()) if fired.size else 0.0

    if fired_fraction >= ROBUST_FRACTION:
        robustness = "ROBUST_POSITIVE"
    elif fired_fraction <= (1.0 - ROBUST_FRACTION):
        robustness = "ROBUST_NEGATIVE"
    else:
        robustness = "FRAGILE"

    return {
        "schema": "oric.multiverse.v1",
        "n_specs": len(outcomes),
        "fired_fraction": round(fired_fraction, 4),
        "robust_fraction_threshold": ROBUST_FRACTION,
        "robustness": robustness,
        "crossing_rate_quartiles": {
            "min": round(float(np.min(rates)), 6) if rates.size else 0.0,
            "q25": round(float(np.quantile(rates, 0.25)), 6) if rates.size else 0.0,
            "median": round(float(np.median(rates)), 6) if rates.size else 0.0,
            "q75": round(float(np.quantile(rates, 0.75)), 6) if rates.size else 0.0,
            "max": round(float(np.max(rates)), 6) if rates.size else 0.0,
        },
        "outcomes": [o.to_dict() for o in outcomes],
    }
