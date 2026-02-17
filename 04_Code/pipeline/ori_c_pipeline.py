#!/usr/bin/env python3
"""
04_Code/pipeline/ori_c_pipeline.py

Canonical ORI-C synthetic simulator.

Goals:
- Deterministic given a seed.
- Columns are explicit and stable across interventions.
- Interventions are discrete and exogenous (no post-observation tuning).

Interventions supported:
- none
- demand_shock
- capacity_hit
- symbolic_cut
- symbolic_injection
- symbolic_cut_then_inject
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Intervention = Literal[
    "none",
    "demand_shock",
    "capacity_hit",
    "symbolic_cut",
    "symbolic_injection",
    "symbolic_cut_then_inject",
]


@dataclass(frozen=True)
class ORICConfig:
    seed: int = 123
    n_steps: int = 200

    # Exogenous schedule
    intervention: Intervention = "none"
    intervention_point: int = 80
    reinjection_point: int = 120

    # Threshold detector for delta_C
    k: float = 2.5
    m: int = 3

    # Scaling
    cap_scale: float = 1000.0

    # Dynamics
    demand_noise: float = 0.03
    ori_drift: float = 0.002
    sigma_to_S_alpha: float = 0.0008

    C_beta: float = 0.40
    C_gamma: float = 0.12

    # Intervention strengths
    demand_shock_factor: float = 1.25
    capacity_hit_factor: float = 0.85
    symbolic_cut_factor: float = 0.20
    symbolic_injection_add: float = 0.25


def _detect_threshold(delta_C: pd.Series, k: float, m: int) -> tuple[int | None, float]:
    x = pd.to_numeric(delta_C, errors="coerce").fillna(0.0)
    mu = float(x.mean())
    sd = float(x.std(ddof=1)) if len(x) > 1 else 0.0
    thr = mu + float(k) * sd
    above = x > thr
    if m <= 1:
        hit = above
    else:
        hit = above.rolling(window=m, min_periods=m).sum() >= m
    if bool(hit.any()):
        return int(hit[hit].index[0]), thr
    return None, thr


def run_oric(cfg: ORICConfig) -> pd.DataFrame:
    rng = np.random.default_rng(int(cfg.seed))

    # Baselines in [0,1]
    O = float(rng.uniform(0.55, 0.85))
    R = float(rng.uniform(0.55, 0.85))
    I = float(rng.uniform(0.55, 0.85))

    # Symbolic stock
    S = float(rng.uniform(0.15, 0.35))

    rows: list[dict] = []
    C = 0.0

    for t in range(int(cfg.n_steps)):
        # small drift (kept exogenous)
        O = float(np.clip(O + rng.normal(0.0, cfg.ori_drift), 0.05, 0.99))
        R = float(np.clip(R + rng.normal(0.0, cfg.ori_drift), 0.05, 0.99))
        I = float(np.clip(I + rng.normal(0.0, cfg.ori_drift), 0.05, 0.99))

        Cap = float(O * R * I * cfg.cap_scale)

        # Demand is exogenous and measured independently from Cap
        base_demand = 0.90 * Cap
        demand = float(base_demand * (1.0 + rng.normal(0.0, cfg.demand_noise)))

        intervention_active = t >= int(cfg.intervention_point)
        reinjection_active = t >= int(cfg.reinjection_point)

        perturb_symbolic = 0.0

        if cfg.intervention == "demand_shock" and intervention_active:
            demand *= float(cfg.demand_shock_factor)

        if cfg.intervention == "capacity_hit" and intervention_active:
            O = float(np.clip(O * cfg.capacity_hit_factor, 0.01, 0.99))
            R = float(np.clip(R * cfg.capacity_hit_factor, 0.01, 0.99))
            I = float(np.clip(I * cfg.capacity_hit_factor, 0.01, 0.99))
            Cap = float(O * R * I * cfg.cap_scale)

        # Symbolic interventions
        if cfg.intervention == "symbolic_cut" and intervention_active:
            S *= float(cfg.symbolic_cut_factor)
            perturb_symbolic = 1.0

        if cfg.intervention == "symbolic_injection" and intervention_active:
            S = float(np.clip(S + cfg.symbolic_injection_add, 0.0, 1.0))
            perturb_symbolic = 1.0

        if cfg.intervention == "symbolic_cut_then_inject":
            if intervention_active:
                S *= float(cfg.symbolic_cut_factor)
                perturb_symbolic = 1.0
            if reinjection_active:
                S = float(np.clip(S + cfg.symbolic_injection_add, 0.0, 1.0))
                perturb_symbolic = 1.0

        Sigma = float(max(0.0, demand - Cap))

        # S accumulates from mismatch (symbolic pressure) with mild decay
        S = float(np.clip(S + cfg.sigma_to_S_alpha * Sigma - 0.002 * S, 0.0, 1.0))

        # Viability proxy: penalize mismatch
        mismatch_frac = Sigma / (Cap + 1e-9)
        V = float(np.clip(1.0 - 1.2 * mismatch_frac, 0.0, 1.0))

        # C updates
        C = float(C + cfg.C_beta * S - cfg.C_gamma * V)

        rows.append(
            {
                "t": t,
                "O": O,
                "R": R,
                "I": I,
                "Cap": Cap,
                "demande_env": demand,
                "Sigma": Sigma,
                "S": S,
                "V": V,
                "C": C,
                "perturb_symbolic": perturb_symbolic,
                "intervention": cfg.intervention,
            }
        )

    df = pd.DataFrame(rows)
    df["delta_C"] = df["C"].diff().fillna(0.0)

    thr_idx, thr_val = _detect_threshold(df["delta_C"], cfg.k, cfg.m)
    df["threshold_value"] = float(thr_val)
    df["threshold_hit"] = 0
    if thr_idx is not None:
        df.loc[thr_idx, "threshold_hit"] = 1

    return df
