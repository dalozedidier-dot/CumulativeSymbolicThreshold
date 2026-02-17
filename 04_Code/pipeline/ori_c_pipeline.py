"""
ORI-C, modèle minimal exécutable (Option B).

Objectifs
- Séparer Cap(t) (capacité) et C(t) (variable d'ordre cumulatif).
- Calculer Sigma(t) à partir de D(E(t)) et Cap(t).
- Mettre à jour un stock symbolique S(t) et une variable d'ordre C(t) sans utiliser V(t) dans la définition de C.
- Produire V(t) en aval, comme mesure externe de viabilité.

Interventions disponibles
- symbolic_cut : dégrade la transmission (réduit les gains sur S et C)
- demand_shock : augmente D(E(t)) à partir de intervention_point
- capacity_hit : réduit O, R, I à partir de intervention_point
- symbolic_injection : injecte une quantité ponctuelle dans S à intervention_point

Option de seuil symbolique (désactivée par défaut)
- Si use_symbolic_threshold = True, C(t) n'accumule que la partie max(0, S(t) - S_star).
  Cela permet de tester une non-linéarité de type seuil sur la couche symbolique sans changer le modèle par défaut.

Toutes les constantes doivent être fixées ex ante lors du test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


Intervention = Literal["none", "symbolic_cut", "demand_shock", "capacity_hit", "symbolic_injection"]


@dataclass(frozen=True)
class ORICConfig:
    seed: int = 42
    n_steps: int = 100

    # Initial ORI states in [0,1]
    init_O: float = 0.70
    init_R: float = 0.65
    init_I: float = 0.68

    # Mild drift to mimic slow adaptation
    drift_O: float = 0.001
    drift_R: float = 0.001
    drift_I: float = 0.001

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

    # Optional symbolic threshold on S used for C updates
    use_symbolic_threshold: bool = False
    S_star: float = 0.0

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
    demand_extra: float = 0.25
    injection_amount: float = 0.20
    injection_once: bool = True


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


def _effective_S_for_C(S: float, use_threshold: bool, S_star: float) -> float:
    if not use_threshold:
        return float(S)
    return float(max(0.0, S - S_star))


def _update_C(C: float, S_for_C: float, beta: float, decay: float, cut: bool) -> float:
    gain = beta * S_for_C
    if cut:
        gain *= 0.25
    C_new = (1.0 - decay) * C + gain
    return float(C_new)


def _viability(Cap: float, sigma: float, C: float, cfg: ORICConfig, rng: np.random.Generator) -> float:
    noise = float(rng.normal(0.0, cfg.V_noise)) if cfg.V_noise > 0 else 0.0
    V = cfg.V_base + cfg.w_cap * Cap - cfg.w_sigma * sigma + cfg.w_C * C + noise
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

    O = float(np.clip(cfg.init_O, 0.0, 1.0))
    R = float(np.clip(cfg.init_R, 0.0, 1.0))
    I = float(np.clip(cfg.init_I, 0.0, 1.0))
    S = 0.05
    C = 0.00

    injection_done = False

    rows = []
    delta_C = []

    for t in range(cfg.n_steps):
        intervention_active = t >= cfg.intervention_point and cfg.intervention != "none"

        cut = False
        demand_extra = 0.0
        inject_now = False

        if intervention_active and cfg.intervention == "symbolic_cut":
            cut = True
        if intervention_active and cfg.intervention == "demand_shock":
            demand_extra = float(cfg.demand_extra)
        if intervention_active and cfg.intervention == "capacity_hit":
            O = max(0.20, O * 0.80)
            R = max(0.20, R * 0.80)
            I = max(0.20, I * 0.80)
        if intervention_active and cfg.intervention == "symbolic_injection":
            if (not cfg.injection_once) or (not injection_done):
                inject_now = True

        demand = _demand(t, cfg.demand_base, cfg.demand_slope) + demand_extra
        Cap = _cap(O, R, I, cfg.cap_scale)
        sigma = _sigma(demand, Cap)

        S_new = _update_S(S, sigma, cfg.alpha_sigma_to_S, cfg.S_decay, cfg.S_floor, cut=cut)
        if inject_now:
            S_new = float(min(1.0, S_new + float(cfg.injection_amount)))
            injection_done = True

        S_for_C = _effective_S_for_C(S_new, cfg.use_symbolic_threshold, cfg.S_star)
        C_new = _update_C(C, S_for_C, cfg.beta_S_to_C, cfg.C_decay, cut=cut)

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
                "S_for_C": S_for_C,
                "C": C_new,
                "delta_C": dC,
                "V": V,
                "intervention": cfg.intervention if intervention_active else "none",
            }
        )

        O = float(np.clip(O + cfg.drift_O, 0.0, 1.0))
        R = float(np.clip(R + cfg.drift_R, 0.0, 1.0))
        I = float(np.clip(I + cfg.drift_I, 0.0, 1.0))

        S, C = S_new, C_new

    delta_C_arr = np.asarray(delta_C, dtype=float)
    hits = detect_threshold(delta_C_arr, k=cfg.k, m=cfg.m, window=cfg.window)

    df = pd.DataFrame(rows)
    df["threshold_hit"] = hits
    return df
