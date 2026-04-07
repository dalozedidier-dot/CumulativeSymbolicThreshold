"""src/oric/ori_core_v2.py — Extended C(t) dynamics with saturation and feedback.

Four model variants for comparison. The V1 reference (ori_core.py) is NOT modified.

V1 (reference):  C(t) = C(t-1) + beta*S - gamma*V
V2 (saturation):  C(t) = C(t-1) + beta*S*(1 - C/C_max) - gamma*V
V3 (feedback):    C(t) = C(t-1) + beta*S_eff*(1 - C/C_max) - gamma*V
                  where S_eff = S*(1 + kappa*C(t-1)) if C(t-1) > C_threshold else S
V4 (SDE):         dC = (beta*S - gamma*V)*dt + sigma_C*dW

Frozen parameters (appended to FROZEN_PARAMS):
  C_max = 10.0
  kappa = 0.05
  C_threshold = 1.0
  sigma_C = 0.02
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


ModelVariant = Literal["V1", "V2", "V3", "V4"]

# Frozen parameters for V2/V3/V4 (must not be tuned post-hoc)
C_MAX = 10.0
KAPPA = 0.05
C_THRESHOLD = 1.0
SIGMA_C = 0.02


@dataclass(frozen=True)
class ModelV2Config:
    """Configuration for extended C(t) dynamics."""
    variant: ModelVariant = "V1"
    C_beta: float = 0.40
    C_gamma: float = 0.12
    C_max: float = C_MAX
    kappa: float = KAPPA
    C_threshold: float = C_THRESHOLD
    sigma_C: float = SIGMA_C
    seed: int = 8000

    # Threshold detector
    k: float = 2.5
    m: int = 3
    baseline_n: int = 50


def compute_C_trajectory(
    S: np.ndarray,
    V: np.ndarray,
    cfg: ModelV2Config,
) -> np.ndarray:
    """Compute C(t) trajectory using the specified model variant.

    Parameters
    ----------
    S : array of symbolic stock values (length n)
    V : array of viability values (length n)
    cfg : ModelV2Config with variant and parameters

    Returns
    -------
    C : array of cumulative symbolic threshold values (length n)
    """
    n = len(S)
    C = np.zeros(n)
    rng = np.random.default_rng(cfg.seed) if cfg.variant == "V4" else None

    for t in range(1, n):
        s_t = float(S[t])
        v_t = float(V[t])
        c_prev = float(C[t - 1])

        if cfg.variant == "V1":
            # Reference: C(t) = C(t-1) + beta*S - gamma*V
            C[t] = c_prev + cfg.C_beta * s_t - cfg.C_gamma * v_t

        elif cfg.variant == "V2":
            # Saturation logistique
            sat = max(0.0, 1.0 - c_prev / cfg.C_max) if cfg.C_max > 0 else 1.0
            C[t] = c_prev + cfg.C_beta * s_t * sat - cfg.C_gamma * v_t

        elif cfg.variant == "V3":
            # Feedback positif conditionnel + saturation
            if c_prev > cfg.C_threshold:
                s_eff = s_t * (1.0 + cfg.kappa * c_prev)
            else:
                s_eff = s_t
            sat = max(0.0, 1.0 - c_prev / cfg.C_max) if cfg.C_max > 0 else 1.0
            C[t] = c_prev + cfg.C_beta * s_eff * sat - cfg.C_gamma * v_t

        elif cfg.variant == "V4":
            # SDE stochastique
            drift = cfg.C_beta * s_t - cfg.C_gamma * v_t
            diffusion = cfg.sigma_C * rng.normal(0, 1)
            C[t] = c_prev + drift + diffusion

        else:
            raise ValueError(f"Unknown variant: {cfg.variant}")

    return C


def detect_threshold(delta_C: np.ndarray, k: float = 2.5, m: int = 3,
                     baseline_n: int = 50) -> tuple[int | None, float]:
    """Detect sustained delta_C threshold crossing.

    Same algorithm as ori_c_pipeline._detect_threshold.
    """
    n = len(delta_C)
    if n == 0:
        return None, 0.0

    bn = max(5, min(baseline_n, n))
    baseline = delta_C[:bn]
    mu = float(np.nanmean(baseline))
    sd = float(np.nanstd(baseline, ddof=0))
    thr = mu + k * sd

    consec = 0
    for i in range(n):
        if float(delta_C[i]) > thr:
            consec += 1
            if consec >= m:
                return i, thr
        else:
            consec = 0

    return None, thr


def run_variant_on_dataframe(
    df: pd.DataFrame,
    variant: ModelVariant,
    cfg: ModelV2Config | None = None,
) -> pd.DataFrame:
    """Run a C(t) variant on a DataFrame that already has S and V columns.

    Adds columns: C_{variant}, delta_C_{variant}, threshold_hit_{variant}.
    Returns a copy with new columns.
    """
    if cfg is None:
        cfg = ModelV2Config(variant=variant)
    else:
        cfg = ModelV2Config(
            variant=variant,
            C_beta=cfg.C_beta, C_gamma=cfg.C_gamma,
            C_max=cfg.C_max, kappa=cfg.kappa,
            C_threshold=cfg.C_threshold, sigma_C=cfg.sigma_C,
            seed=cfg.seed, k=cfg.k, m=cfg.m, baseline_n=cfg.baseline_n,
        )

    S = df["S"].values.astype(float) if "S" in df.columns else np.zeros(len(df))
    V = df["V"].values.astype(float) if "V" in df.columns else np.ones(len(df)) * 0.5

    C = compute_C_trajectory(S, V, cfg)
    delta_C = np.diff(C, prepend=0.0)
    thr_idx, thr_val = detect_threshold(delta_C, cfg.k, cfg.m, cfg.baseline_n)

    result = df.copy()
    result[f"C_{variant}"] = C
    result[f"delta_C_{variant}"] = delta_C
    result[f"threshold_value_{variant}"] = thr_val
    result[f"threshold_hit_{variant}"] = 0
    if thr_idx is not None:
        result.loc[thr_idx, f"threshold_hit_{variant}"] = 1

    return result


def compare_all_variants(
    df: pd.DataFrame,
    seed: int = 8000,
) -> dict:
    """Run all 4 variants and return comparison summary."""
    base_cfg = ModelV2Config(seed=seed)
    results = {}

    for variant in ["V1", "V2", "V3", "V4"]:
        df = run_variant_on_dataframe(df, variant, base_cfg)

        c_col = f"C_{variant}"
        hit_col = f"threshold_hit_{variant}"
        thr_col = f"threshold_value_{variant}"

        hit_idx = None
        if (df[hit_col] > 0).any():
            hit_idx = int(df.index[df[hit_col] > 0][0])

        c_vals = df[c_col].values
        n = len(c_vals)
        mid = n // 2

        # Effect size (Cohen's d)
        pre = c_vals[:mid]
        post = c_vals[mid:]
        pooled_sd = np.sqrt((np.var(pre) + np.var(post)) / 2)
        cohens_d = (np.mean(post) - np.mean(pre)) / max(pooled_sd, 1e-12)

        results[variant] = {
            "verdict": "ACCEPT" if hit_idx is not None else "INDETERMINATE",
            "threshold_hit_idx": hit_idx,
            "threshold_value": float(df[thr_col].iloc[0]),
            "C_mean": float(np.mean(c_vals)),
            "C_max": float(np.max(c_vals)),
            "effect_size_d": float(cohens_d),
        }

    return results, df
