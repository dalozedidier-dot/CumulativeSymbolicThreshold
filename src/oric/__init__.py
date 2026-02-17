"""ORI-C canonical package.

This package provides:
- ORI core computations: O, R, I, Cap, Sigma, V
- Symbolic layer computations: S, C, regimes, cut U
- Randomization and logging utilities for reproducible experiments

The package is intentionally minimal. It is designed to be used by scripts in `04_Code/pipeline/`.
"""

from .prereg import PreregSpec
from .randomization import RandomizationEngine
from .logger import ExperimentLogger
from .ori_core import compute_cap_projection, compute_sigma, compute_viability, summarize_run
from .symbolic import compute_stock_S, compute_order_C, detect_s_star_piecewise

__all__ = [
    "PreregSpec",
    "RandomizationEngine",
    "ExperimentLogger",
    "compute_cap_projection",
    "compute_sigma",
    "compute_viability",
    "summarize_run",
    "compute_stock_S",
    "compute_order_C",
    "detect_s_star_piecewise",
]
