"""placebo.py — Versioned placebo battery for specificity testing.

The old cyclic-shift-only placebo detected at 100%, proving the detector
was non-specific.  This module provides multiple null-generation strategies
that destroy different aspects of the causal structure while preserving
marginal statistics.

Placebo strategies:
  1. cyclic_shift     : rows shifted by N // 3 (preserves autocorrelation)
  2. temporal_permute : random permutation of row order (destroys all temporal)
  3. phase_randomize  : FFT-based phase randomization (preserves power spectrum)
  4. proxy_remap      : O/R/I columns shuffled across variables (breaks mapping)
  5. block_shuffle    : blocks of rows shuffled (partially preserves local structure)

Each strategy has a known signature of what it preserves and destroys:
  - autocorrelation, spectral density, marginal distribution, cross-correlation

The placebo battery verdict is: non-detection rate across ALL strategies
must exceed the contractual threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


PlaceboStrategy = Literal[
    "cyclic_shift",
    "temporal_permute",
    "phase_randomize",
    "proxy_remap",
    "block_shuffle",
]

ALL_STRATEGIES: tuple[PlaceboStrategy, ...] = (
    "cyclic_shift",
    "temporal_permute",
    "phase_randomize",
    "proxy_remap",
    "block_shuffle",
)


@dataclass(frozen=True)
class PlaceboSpec:
    """Metadata for a placebo generation."""
    strategy: PlaceboStrategy
    seed: int
    preserves: tuple[str, ...]
    destroys: tuple[str, ...]


# ── Strategy registry ──────────────────────────────────────────────────────

_STRATEGY_META: dict[PlaceboStrategy, dict] = {
    "cyclic_shift": {
        "preserves": ("autocorrelation", "spectral_density", "marginal"),
        "destroys": ("temporal_alignment",),
    },
    "temporal_permute": {
        "preserves": ("marginal",),
        "destroys": ("autocorrelation", "temporal_alignment", "cross_correlation"),
    },
    "phase_randomize": {
        "preserves": ("spectral_density", "marginal_approx"),
        "destroys": ("phase_coupling", "temporal_alignment"),
    },
    "proxy_remap": {
        "preserves": ("autocorrelation", "temporal_alignment", "marginal"),
        "destroys": ("cross_correlation", "causal_mapping"),
    },
    "block_shuffle": {
        "preserves": ("local_autocorrelation", "marginal"),
        "destroys": ("global_temporal", "long_range_dependence"),
    },
}


# ── Generators ─────────────────────────────────────────────────────────────

def make_cyclic_shift(df: pd.DataFrame, seed: int,
                      shift_divisor: int = 3) -> tuple[pd.DataFrame, PlaceboSpec]:
    """Cyclic shift by N // shift_divisor rows."""
    shift = max(1, len(df) // shift_divisor)
    out = pd.concat([df.iloc[shift:], df.iloc[:shift]], ignore_index=True)
    meta = _STRATEGY_META["cyclic_shift"]
    return out, PlaceboSpec(
        strategy="cyclic_shift", seed=seed,
        preserves=meta["preserves"], destroys=meta["destroys"],
    )


def make_temporal_permute(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, PlaceboSpec]:
    """Full random permutation of row order."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(df))
    out = df.iloc[idx].reset_index(drop=True)
    meta = _STRATEGY_META["temporal_permute"]
    return out, PlaceboSpec(
        strategy="temporal_permute", seed=seed,
        preserves=meta["preserves"], destroys=meta["destroys"],
    )


def _phase_randomize_series(arr: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Phase-randomize a 1D array using FFT."""
    n = len(arr)
    if n < 4:
        return arr.copy()
    ft = np.fft.rfft(arr)
    phases = rng.uniform(0, 2 * np.pi, size=len(ft))
    # Keep DC and Nyquist real
    phases[0] = 0.0
    if n % 2 == 0:
        phases[-1] = 0.0
    ft_rand = ft * np.exp(1j * phases)
    result = np.fft.irfft(ft_rand, n=n)
    return result


def make_phase_randomize(df: pd.DataFrame, seed: int,
                         columns: list[str] | None = None) -> tuple[pd.DataFrame, PlaceboSpec]:
    """FFT-based phase randomization of numeric columns."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    if columns is None:
        columns = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    for col in columns:
        vals = df[col].to_numpy(dtype=float).copy()
        if np.all(np.isnan(vals)):
            continue
        # Fill NaN for FFT
        mask = np.isnan(vals)
        vals[mask] = np.nanmean(vals)
        out[col] = _phase_randomize_series(vals, rng)
    meta = _STRATEGY_META["phase_randomize"]
    return out, PlaceboSpec(
        strategy="phase_randomize", seed=seed,
        preserves=meta["preserves"], destroys=meta["destroys"],
    )


def make_proxy_remap(df: pd.DataFrame, seed: int,
                     proxy_columns: list[str] | None = None) -> tuple[pd.DataFrame, PlaceboSpec]:
    """Shuffle ORI-C proxy columns across variables.

    This preserves each column's time series but breaks the O→R→I→demand
    mapping.  If the detector relies on the correct causal structure,
    this should produce NOT_DETECTED.
    """
    rng = np.random.default_rng(seed)
    out = df.copy()
    if proxy_columns is None:
        proxy_columns = [c for c in ("O", "R", "I", "demand", "S") if c in df.columns]
    if len(proxy_columns) < 2:
        meta = _STRATEGY_META["proxy_remap"]
        return out, PlaceboSpec(
            strategy="proxy_remap", seed=seed,
            preserves=meta["preserves"], destroys=meta["destroys"],
        )

    # Permute columns
    perm = rng.permutation(len(proxy_columns)).tolist()
    # Ensure it's actually a permutation (not identity)
    while perm == list(range(len(proxy_columns))) and len(proxy_columns) > 1:
        perm = rng.permutation(len(proxy_columns)).tolist()

    remapped = {}
    for i, col in enumerate(proxy_columns):
        remapped[col] = df[proxy_columns[perm[i]]].values

    for col, vals in remapped.items():
        out[col] = vals

    meta = _STRATEGY_META["proxy_remap"]
    return out, PlaceboSpec(
        strategy="proxy_remap", seed=seed,
        preserves=meta["preserves"], destroys=meta["destroys"],
    )


def make_block_shuffle(df: pd.DataFrame, seed: int,
                       block_size: int | None = None) -> tuple[pd.DataFrame, PlaceboSpec]:
    """Shuffle blocks of consecutive rows.

    Block size defaults to N // 10 (at least 5 rows per block).
    """
    rng = np.random.default_rng(seed)
    n = len(df)
    if block_size is None:
        block_size = max(5, n // 10)

    n_blocks = n // block_size
    remainder = n % block_size

    blocks = [df.iloc[i * block_size:(i + 1) * block_size] for i in range(n_blocks)]
    if remainder > 0:
        blocks.append(df.iloc[n_blocks * block_size:])

    perm = rng.permutation(len(blocks)).tolist()
    out = pd.concat([blocks[i] for i in perm], ignore_index=True)

    meta = _STRATEGY_META["block_shuffle"]
    return out, PlaceboSpec(
        strategy="block_shuffle", seed=seed,
        preserves=meta["preserves"], destroys=meta["destroys"],
    )


# ── Battery runner ─────────────────────────────────────────────────────────

_GENERATORS = {
    "cyclic_shift": make_cyclic_shift,
    "temporal_permute": make_temporal_permute,
    "phase_randomize": make_phase_randomize,
    "proxy_remap": make_proxy_remap,
    "block_shuffle": make_block_shuffle,
}


def generate_placebo(
    df: pd.DataFrame,
    strategy: PlaceboStrategy,
    seed: int,
    **kwargs,
) -> tuple[pd.DataFrame, PlaceboSpec]:
    """Generate a single placebo using the specified strategy."""
    gen = _GENERATORS[strategy]
    return gen(df, seed, **kwargs)


def generate_placebo_battery(
    df: pd.DataFrame,
    strategies: tuple[PlaceboStrategy, ...] | None = None,
    seed: int = 42,
) -> list[tuple[pd.DataFrame, PlaceboSpec]]:
    """Generate placebos for all strategies in the battery.

    Returns a list of (dataframe, spec) tuples.
    """
    if strategies is None:
        strategies = ALL_STRATEGIES

    results = []
    for i, strat in enumerate(strategies):
        sub_seed = seed + i * 1000
        df_placebo, spec = generate_placebo(df, strat, sub_seed)
        results.append((df_placebo, spec))

    return results


@dataclass
class PlaceboBatteryResult:
    """Aggregate result from running the placebo battery."""
    n_strategies: int = 0
    n_detected: int = 0
    n_not_detected: int = 0
    n_indeterminate: int = 0
    detection_rate: float = 0.0
    non_detection_rate: float = 0.0
    per_strategy: list[dict] = None  # type: ignore[assignment]
    battery_passes: bool = False

    def __post_init__(self):
        if self.per_strategy is None:
            self.per_strategy = []

    def to_dict(self) -> dict:
        return {
            "n_strategies": self.n_strategies,
            "n_detected": self.n_detected,
            "n_not_detected": self.n_not_detected,
            "n_indeterminate": self.n_indeterminate,
            "detection_rate": self.detection_rate,
            "non_detection_rate": self.non_detection_rate,
            "battery_passes": self.battery_passes,
            "per_strategy": self.per_strategy,
        }


def evaluate_placebo_battery(
    per_strategy_verdicts: list[tuple[PlaceboStrategy, str]],
    max_fp_rate: float = 0.20,
) -> PlaceboBatteryResult:
    """Evaluate the battery: each verdict is DETECTED/NOT_DETECTED/INDETERMINATE.

    battery_passes if false-positive (detection) rate <= max_fp_rate.
    """
    n = len(per_strategy_verdicts)
    n_det = sum(1 for _, v in per_strategy_verdicts if v == "DETECTED")
    n_not = sum(1 for _, v in per_strategy_verdicts if v == "NOT_DETECTED")
    n_ind = sum(1 for _, v in per_strategy_verdicts if v == "INDETERMINATE")
    n_decidable = n_det + n_not

    det_rate = n_det / n_decidable if n_decidable > 0 else 0.0
    non_det_rate = n_not / n_decidable if n_decidable > 0 else 0.0

    per_strat = [
        {"strategy": s, "verdict": v}
        for s, v in per_strategy_verdicts
    ]

    return PlaceboBatteryResult(
        n_strategies=n,
        n_detected=n_det,
        n_not_detected=n_not,
        n_indeterminate=n_ind,
        detection_rate=det_rate,
        non_detection_rate=non_det_rate,
        per_strategy=per_strat,
        battery_passes=det_rate <= max_fp_rate,
    )
