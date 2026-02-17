#!/usr/bin/env python3
# bcm_plasticity.py
#
# Minimal BCM-like plasticity simulator.
#
# Designed as an optional "neuro extension" module:
# - deterministic with a seed
# - lightweight (numpy only)
# - usable for cut and reinjection schedules

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BCMConfig:
    n_steps: int = 1200
    seed: int = 42

    # Input drive
    input_amp: float = 0.7
    noise_sigma: float = 0.05

    # Plasticity
    eta: float = 0.002
    tau_bar: float = 80.0
    c0: float = 0.25
    p: float = 2.0

    # Weight constraints
    w0: float = 0.6
    w_min: float = 0.0
    w_max: float = 2.0


def simulate_bcm(cfg: BCMConfig, x: Optional[np.ndarray] = None) -> Tuple[pd.DataFrame, Dict[str, float]]:
    rng = np.random.default_rng(cfg.seed)
    n = cfg.n_steps

    if x is None:
        x = np.full(n, cfg.input_amp, dtype=float)
    else:
        x = np.asarray(x, dtype=float)
        if x.shape[0] != n:
            raise ValueError(f"Input x length {x.shape[0]} != n_steps {n}")

    w = float(cfg.w0)
    c_bar = float(cfg.c0**2)

    rows = []
    for t in range(n):
        c = w * float(x[t]) + float(rng.normal(0.0, cfg.noise_sigma))
        c = max(0.0, c)

        c2 = c * c
        c_bar = c_bar + (c2 - c_bar) / float(cfg.tau_bar)

        theta_m = (c_bar / float(cfg.c0)) ** float(cfg.p) * c_bar
        phi = c * (c - theta_m)

        w = float(np.clip(w + float(cfg.eta) * float(x[t]) * phi, float(cfg.w_min), float(cfg.w_max)))

        rows.append(
            {
                "t": t,
                "x": float(x[t]),
                "c": c,
                "c_bar": float(c_bar),
                "theta_M": float(theta_m),
                "phi": float(phi),
                "w": w,
            }
        )

    df = pd.DataFrame(rows)

    early = df.iloc[: max(1, n // 3)]
    late = df.iloc[max(1, 2 * n // 3) :]

    metrics = {
        "w_start": float(df["w"].iloc[0]),
        "w_end": float(df["w"].iloc[-1]),
        "w_delta_end_minus_start": float(df["w"].iloc[-1] - df["w"].iloc[0]),
        "phi_pos_frac_late": float(np.mean(late["phi"] > 0.0)) if len(late) else 0.0,
        "cross_frac_late": float(np.mean(late["c"] > late["theta_M"])) if len(late) else 0.0,
        "c_mean_early": float(early["c"].mean()),
        "c_mean_late": float(late["c"].mean()) if len(late) else float("nan"),
    }
    return df, metrics


def build_input_schedule(
    n_steps: int,
    input_amp: float,
    cut_start: Optional[int] = None,
    cut_len: int = 0,
    reinject_start: Optional[int] = None,
    reinject_len: int = 0,
    reinject_amp: Optional[float] = None,
) -> np.ndarray:
    x = np.full(int(n_steps), float(input_amp), dtype=float)

    if cut_start is not None and int(cut_len) > 0:
        cs = int(max(0, cut_start))
        ce = int(min(n_steps, cs + int(cut_len)))
        x[cs:ce] = 0.0

    if reinject_start is not None and int(reinject_len) > 0:
        rs = int(max(0, reinject_start))
        re = int(min(n_steps, rs + int(reinject_len)))
        amp = float(reinject_amp) if reinject_amp is not None else float(input_amp)
        x[rs:re] = amp

    return x
