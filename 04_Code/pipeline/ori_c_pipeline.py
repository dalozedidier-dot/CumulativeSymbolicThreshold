#!/usr/bin/env python3
"""
04_Code/pipeline/ori_c_pipeline.py

Canonical ORI-C synthetic simulator.

Goals
- Deterministic given a seed.
- Columns are explicit and stable across interventions.
- Interventions are discrete and exogenous (no post-observation tuning).

Interventions supported
- none
- demand_shock
- capacity_hit
- symbolic_cut
- symbolic_injection
- symbolic_cut_then_inject

Notes (validation needs)
- sigma_star (Sigma*) allows a "cumulative threshold" regime where symbolic accumulation only starts
  when Sigma(t) exceeds Sigma*.
- S_decay can be linked to a time constant tau via S_decay = 1/tau.
- intervention_duration supports hysteresis-style scenarios (shock on, then off) without changing
  the core mechanics.

Backwards compatibility
- Some older scripts expect to override initial states. We support optional O0,R0,I0,S0.
"""

from __future__ import annotations

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

    # Optional explicit initial conditions (for matched experiments)
    O0: float | None = None
    R0: float | None = None
    I0: float | None = None
    S0: float | None = None

    # Exogenous schedule
    intervention: Intervention = "none"
    intervention_point: int = 80
    reinjection_point: int = 120
    intervention_duration: int = 0  # 0 means "until the end"

    # Threshold detector for delta_C (baseline estimation)
    k: float = 2.5
    m: int = 3
    baseline_n: int = 30

    # Scaling
    cap_scale: float = 1000.0

    # Dynamics
    demand_noise: float = 0.03
    ori_drift: float = 0.002
    ori_trend: float = 0.0

    # Symbolic accumulation gate and decay
    sigma_star: float = 0.0
    sigma_to_S_alpha: float = 0.0008
    S_decay: float = 0.002

    # C dynamics
    C_beta: float = 0.40
    C_gamma: float = 0.12

    # Intervention strengths
    demand_shock_factor: float = 1.25
    capacity_hit_factor: float = 0.85
    symbolic_cut_factor: float = 0.20
    symbolic_injection_add: float = 0.25


def _detect_threshold(delta_C: pd.Series, k: float, m: int, baseline_n: int) -> tuple[int | None, float]:
    """Detect sustained delta_C threshold crossing.

    We estimate (mu, sigma) on the first `baseline_n` points, then define:
      thr = mu + k * sigma

    A hit occurs when delta_C > thr for m consecutive steps.
    """

    x = pd.to_numeric(delta_C, errors="coerce").fillna(0.0).reset_index(drop=True)
    n = int(len(x))
    if n == 0:
        return None, 0.0

    bn = int(baseline_n)
    if bn < 5:
        bn = 5
    bn = min(bn, n)

    baseline = x.iloc[:bn]
    mu = float(baseline.mean())
    sd = float(baseline.std(ddof=0))

    thr = mu + float(k) * sd

    consec = 0
    for i, v in enumerate(x.to_numpy()):
        if float(v) > thr:
            consec += 1
            if consec >= int(m):
                return int(i), float(thr)
        else:
            consec = 0

    return None, float(thr)


def _active_window(t: int, start: int, duration: int) -> bool:
    if t < int(start):
        return False
    if int(duration) <= 0:
        return True
    return t < int(start) + int(duration)


def run_oric(cfg: ORICConfig) -> pd.DataFrame:
    rng = np.random.default_rng(int(cfg.seed))

    # Baselines in [0,1]
    O = float(rng.uniform(0.55, 0.85))
    R = float(rng.uniform(0.55, 0.85))
    I = float(rng.uniform(0.55, 0.85))

    # Symbolic stock
    S = float(rng.uniform(0.15, 0.35))

    # Optional overrides for matched experiments
    if cfg.O0 is not None:
        O = float(np.clip(cfg.O0, 0.01, 0.99))
    if cfg.R0 is not None:
        R = float(np.clip(cfg.R0, 0.01, 0.99))
    if cfg.I0 is not None:
        I = float(np.clip(cfg.I0, 0.01, 0.99))
    if cfg.S0 is not None:
        S = float(np.clip(cfg.S0, 0.0, 1.0))

    rows: list[dict] = []
    C = 0.0

    for t in range(int(cfg.n_steps)):
        # small drift (kept exogenous)
        O = float(np.clip(O + float(cfg.ori_trend) + rng.normal(0.0, cfg.ori_drift), 0.05, 0.99))
        R = float(np.clip(R + float(cfg.ori_trend) + rng.normal(0.0, cfg.ori_drift), 0.05, 0.99))
        I = float(np.clip(I + float(cfg.ori_trend) + rng.normal(0.0, cfg.ori_drift), 0.05, 0.99))

        Cap = float(O * R * I * cfg.cap_scale)

        # Demand is exogenous and measured independently from Cap
        base_demand = 0.90 * Cap
        demand = float(base_demand * (1.0 + rng.normal(0.0, cfg.demand_noise)))

        intervention_active = _active_window(t, int(cfg.intervention_point), int(cfg.intervention_duration))
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

        # Symbolic gate: accumulation starts only above Sigma*
        Sigma_symbolic = float(max(0.0, Sigma - float(cfg.sigma_star)))

        # S accumulates from mismatch (symbolic pressure) with decay
        S = float(np.clip(S + cfg.sigma_to_S_alpha * Sigma_symbolic - float(cfg.S_decay) * S, 0.0, 1.0))

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
                # dual naming for compatibility
                "demand": demand,
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

    thr_idx, thr_val = _detect_threshold(df["delta_C"], cfg.k, cfg.m, cfg.baseline_n)
    df["threshold_value"] = float(thr_val)
    df["threshold_hit"] = 0
    if thr_idx is not None:
        df.loc[thr_idx, "threshold_hit"] = 1

    return df




def _auto_cap_scale_from_demand(
    base_cap: np.ndarray,
    demand: np.ndarray,
    *,
    cap_scale_default: float,
    demand_to_cap_ratio: float = 0.90,
) -> float:
    """Estimate a cap_scale so that median(demand) ~= demand_to_cap_ratio * median(Cap).

    Cap is computed as Cap = base_cap * cap_scale, where base_cap = O * R * I in [0,1].
    This is a pragmatic alignment for real data where demand is in an arbitrary unit.
    """
    x = np.asarray(base_cap, dtype=float)
    d = np.asarray(demand, dtype=float)
    if len(x) == 0:
        return float(cap_scale_default)
    if len(d) == 0 or np.all(~np.isfinite(d)):
        return float(cap_scale_default)

    x_med = float(np.nanmedian(x))
    d_med = float(np.nanmedian(d))
    if not np.isfinite(x_med) or x_med <= 1e-12 or not np.isfinite(d_med) or d_med <= 0.0:
        return float(cap_scale_default)

    scale = d_med / (float(demand_to_cap_ratio) * x_med + 1e-12)
    if not np.isfinite(scale) or scale <= 0.0:
        return float(cap_scale_default)
    return float(scale)


def run_oric_from_observations(
    df_obs: pd.DataFrame,
    cfg: ORICConfig,
    *,
    col_t: str = "t",
    col_O: str = "O",
    col_R: str = "R",
    col_I: str = "I",
    col_demand: str = "demand",
    col_S: str | None = None,
    auto_scale: bool = True,
    demand_to_cap_ratio: float = 0.90,
) -> pd.DataFrame:
    """Run ORI-C mechanics on observed (real) time series.

    The observed series provides O(t), R(t), I(t) in [0,1] and optionally demand(t).
    If col_S is provided, S(t) is taken as observed (clipped to [0,1]) and the internal
    symbolic accumulation step is skipped. Otherwise, S(t) evolves from Sigma(t) with
    the same gate and decay as the synthetic simulator.

    The goal is to produce the same core columns as synthetic runs:
    t, O, R, I, Cap, demand, Sigma, S, V, C, delta_C, threshold_value, threshold_hit.

    This function does not apply discrete interventions.
    """
    df = df_obs.copy()

    if col_t not in df.columns:
        raise ValueError(f"Missing required time column: {col_t}")
    for c in [col_O, col_R, col_I]:
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")

    t = pd.to_numeric(df[col_t], errors="coerce").fillna(0).astype(int).to_numpy()
    O = pd.to_numeric(df[col_O], errors="coerce").astype(float).to_numpy()
    R = pd.to_numeric(df[col_R], errors="coerce").astype(float).to_numpy()
    I = pd.to_numeric(df[col_I], errors="coerce").astype(float).to_numpy()

    # Basic clipping for numeric safety
    O = np.clip(O, 0.01, 0.99)
    R = np.clip(R, 0.01, 0.99)
    I = np.clip(I, 0.01, 0.99)

    base_cap = O * R * I

    demand = None
    if col_demand in df.columns:
        demand = pd.to_numeric(df[col_demand], errors="coerce").astype(float).to_numpy()
    else:
        demand = np.full(len(base_cap), np.nan, dtype=float)

    cap_scale = float(cfg.cap_scale)
    if bool(auto_scale):
        cap_scale = _auto_cap_scale_from_demand(
            base_cap,
            demand,
            cap_scale_default=float(cfg.cap_scale),
            demand_to_cap_ratio=float(demand_to_cap_ratio),
        )

    Cap = base_cap * cap_scale

    # If demand is missing, use the synthetic convention demand ~= 0.90 * Cap
    if np.all(~np.isfinite(demand)):
        demand = float(demand_to_cap_ratio) * Cap

    # Prepare S source
    use_S_obs = (col_S is not None) and (col_S in df.columns)
    if use_S_obs:
        S_obs = pd.to_numeric(df[col_S], errors="coerce").astype(float).to_numpy()
        S_obs = np.clip(np.nan_to_num(S_obs, nan=0.0), 0.0, 1.0)
    else:
        S_obs = None

    # Initial S
    if cfg.S0 is not None:
        S = float(np.clip(cfg.S0, 0.0, 1.0))
    elif use_S_obs and S_obs is not None and len(S_obs) > 0:
        S = float(S_obs[0])
    else:
        S = 0.20

    C = 0.0
    rows: list[dict] = []

    for i in range(int(len(t))):
        Sigma = float(max(0.0, float(demand[i]) - float(Cap[i])))

        if use_S_obs and S_obs is not None:
            S = float(S_obs[i])
            Sigma_symbolic = float(max(0.0, Sigma - float(cfg.sigma_star)))
        else:
            Sigma_symbolic = float(max(0.0, Sigma - float(cfg.sigma_star)))
            S = float(np.clip(S + cfg.sigma_to_S_alpha * Sigma_symbolic - float(cfg.S_decay) * S, 0.0, 1.0))

        mismatch_frac = Sigma / (float(Cap[i]) + 1e-9)
        V = float(np.clip(1.0 - 1.2 * mismatch_frac, 0.0, 1.0))

        C = float(C + cfg.C_beta * S - cfg.C_gamma * V)

        rows.append(
            {
                "t": int(t[i]),
                "O": float(O[i]),
                "R": float(R[i]),
                "I": float(I[i]),
                "Cap": float(Cap[i]),
                "demand": float(demand[i]),
                "Sigma": float(Sigma),
                "Sigma_symbolic": float(Sigma_symbolic),
                "S": float(S),
                "V": float(V),
                "C": float(C),
                "intervention": "real",
            }
        )

    out = pd.DataFrame(rows)
    out["delta_C"] = out["C"].diff().fillna(0.0)

    thr_idx, thr_val = _detect_threshold(out["delta_C"], cfg.k, cfg.m, cfg.baseline_n)
    out["threshold_value"] = float(thr_val)
    out["threshold_hit"] = 0
    if thr_idx is not None:
        out.loc[thr_idx, "threshold_hit"] = 1

    # Keep alignment info
    out["cap_scale_used"] = float(cap_scale)
    out["demand_to_cap_ratio"] = float(demand_to_cap_ratio)
    out["S_is_observed"] = bool(use_S_obs)

    return out


# Backwards compatibility wrapper: older scripts refer to generate_oric_synth

def generate_oric_synth(cfg: ORICConfig, seed: int | None = None) -> pd.DataFrame:
    if seed is None:
        return run_oric(cfg)
    return run_oric(ORICConfig(**{**cfg.__dict__, "seed": int(seed)}))
