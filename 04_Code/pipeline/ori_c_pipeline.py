"""
ORI-C, modèle minimal exécutable (Option B).

Objectif:
- Séparer Cap(t) (capacité) et C(t) (variable d'ordre cumulatif).
- Calculer Sigma(t) à partir de D(E(t)) et Cap(t).
- Mettre à jour un stock symbolique S(t) et une variable d'ordre C(t) sans utiliser V(t) dans la définition de C.
- Produire V(t) en aval, comme mesure externe de viabilité.

Interventions:
- symbolic_cut: dégrade la transmission (réduit S et le gain de C)
- demand_shock: augmente D(E(t))
- capacity_hit: réduit O, R, I

Toutes les constantes doivent être fixées ex ante lors du test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


Intervention = Literal["none", "symbolic_cut", "demand_shock", "capacity_hit"]


@dataclass(frozen=True)
class ORICConfig:
    seed: int = 42
    n_steps: int = 100

    # D(E) baseline and dynamics
    demand_base: float = 1.20
    demand_slope: float = 0.004

    # Cap(O,R,I)
    cap_scale: float = 2.20

    # Symbolic stock S dynamics
    alpha_sigma_to_S: float = 0.08
    S_decay: float = 0.02
    S_floor: float = 0.0

    # Order parameter C dynamics
    beta_S_to_C: float = 0.06
    C_decay: float = 0.005

    # Viability mapping
    V_base: float = 0.55
    w_cap: float = 0.30
    w_sigma: float = 0.25
    w_C: float = 0.20
    V_noise: float = 0.0

    # Threshold detection
    k: float = 2.5
    m: int = 3
    window: int = 10

    # Intervention
    intervention_point: int = 70
    intervention: Intervention = "none"


def _cap(O: float, R: float, I: float, cap_scale: float) -> float:
    return cap_scale * (O * R * I)


def _demand(t: int, base: float, slope: float) -> float:
    return base + slope * float(t)


def _sigma(demand: float, cap: float) -> float:
    return max(0.0, demand - cap)


def _update_S(S: float, sigma: float, alpha: float, decay: float, floor: float, cut: bool) -> float:
    gain = alpha * sigma
    if cut:
        gain *= 0.25
    S_new = (1.0 - decay) * S + gain
    return max(floor, float(S_new))


def _update_C(C: float, S: float, beta: float, decay: float, cut: bool) -> float:
    gain = beta * S
    if cut:
        gain *= 0.25
    C_new = (1.0 - decay) * C + gain
    return float(C_new)


def _viability(Cap: float, sigma: float, C: float, cfg: ORICConfig, rng: np.random.Generator) -> float:
    noise = float(rng.normal(0.0, cfg.V_noise)) if cfg.V_noise > 0 else 0.0
    V = cfg.V_base + cfg.w_cap * Cap - cfg.w_sigma * sigma + cfg.w_C * C + noise
    # clamp to [0, 1] for demo
    return float(np.clip(V, 0.0, 1.0))


def detect_threshold(delta_C: np.ndarray, k: float, m: int, window: int) -> np.ndarray:
    n = len(delta_C)
    hits = np.zeros(n, dtype=int)
    if n < window + 1:
        return hits

    run = 0
    for t in range(n):
        if t < window:
            continue
        ref = delta_C[t - window : t]
        mu = float(np.mean(ref))
        sigma = float(np.std(ref, ddof=1)) if len(ref) > 1 else 0.0
        thr = mu + k * sigma
        ok = float(delta_C[t]) > thr
        run = run + 1 if ok else 0
        if run >= m:
            hits[t - m + 1] = 1
    return hits


def run_oric(cfg: ORICConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed)

    # states O,R,I in [0,1]
    O, R, I = 0.70, 0.65, 0.68
    S = 0.05
    C = 0.00

    rows = []
    delta_C = []

    for t in range(cfg.n_steps):
        intervention_active = t >= cfg.intervention_point and cfg.intervention != "none"

        # Apply interventions
        cut = False
        demand_extra = 0.0
        if intervention_active and cfg.intervention == "symbolic_cut":
            cut = True
        if intervention_active and cfg.intervention == "demand_shock":
            demand_extra = 0.25
        if intervention_active and cfg.intervention == "capacity_hit":
            O = max(0.20, O * 0.80)
            R = max(0.20, R * 0.80)
            I = max(0.20, I * 0.80)

        demand = _demand(t, cfg.demand_base, cfg.demand_slope) + demand_extra
        Cap = _cap(O, R, I, cfg.cap_scale)
        sigma = _sigma(demand, Cap)

        S_new = _update_S(S, sigma, cfg.alpha_sigma_to_S, cfg.S_decay, cfg.S_floor, cut=cut)
        C_new = _update_C(C, S_new, cfg.beta_S_to_C, cfg.C_decay, cut=cut)

        V = _viability(Cap, sigma, C_new, cfg, rng)

        dC = C_new - C
        delta_C.append(dC)

        rows.append(
            {
                "t": t,
                "O": O,
                "R": R,
                "I": I,
                "demand": demand,
                "Cap": Cap,
                "Sigma": sigma,
                "S": S_new,
                "C": C_new,
                "delta_C": dC,
                "V": V,
                "intervention": cfg.intervention if intervention_active else "none",
            }
        )

        # mild drift to mimic adaptation
        O = float(np.clip(O + 0.001, 0.0, 1.0))
        R = float(np.clip(R + 0.001, 0.0, 1.0))
        I = float(np.clip(I + 0.001, 0.0, 1.0))

        S, C = S_new, C_new

    delta_C_arr = np.asarray(delta_C, dtype=float)
    hits = detect_threshold(delta_C_arr, k=cfg.k, m=cfg.m, window=cfg.window)

    df = pd.DataFrame(rows)
    df["threshold_hit"] = hits
    return df
