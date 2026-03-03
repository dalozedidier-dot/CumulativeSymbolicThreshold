"""generate_synth.py — Synthetic data generator for the Climate sector panel.

Two pilots:

  co2_mauna_loa : CO₂ accumulation dynamics with emission reduction intervention
  gistemp       : Temperature anomaly series with tipping-point risk scenario

ORI-C mappings (mirroring fetch_real_data.py):

  co2_mauna_loa:
    O(t) = 1 − CO₂_acceleration   (ecosystem org capacity)
    R(t) = 1 − rolling_volatility  (climate resilience)
    I(t) = seasonal_regularity     (system integration)
    S(t) = fraction_below_350ppm   (symbolic safety stock)
    demand(t) = CO₂_excess_norm

  gistemp:
    O(t) = 1 − T_anomaly_pos       (capacity below critical threshold)
    R(t) = 1 − rolling_T_std       (temperature stability)
    I(t) = hemispheric_coherence    (land-ocean coupling)
    S(t) = fraction_below_1C        (symbolic safety stock)
    demand(t) = T_anomaly_norm
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# ── CO₂ synthetic generator ───────────────────────────────────────────────────

def _generate_co2(n: int, seed: int) -> pd.DataFrame:
    """Simulate CO₂ ppm series with:
    - Phase 1 (0 → n//2): unregulated growth (acceleration ↑)
    - Phase 2 (n//2 → end): emission reduction intervention (growth stabilises)
    """
    rng = np.random.default_rng(seed)

    co2 = np.zeros(n)
    co2[0] = 315.0  # 1958 baseline (Mauna Loa start)

    t_intervention = n // 2
    # Annual growth rates
    growth_pre  = 1.5   # ppm/year pre-intervention (accelerating)
    growth_post = 0.8   # ppm/year post-intervention (stabilising)

    for t in range(1, n):
        if t < t_intervention:
            # Accelerating growth — symbolic regime pre-seuil
            accel  = 0.02 * (t / t_intervention)   # increasing acceleration
            growth = growth_pre + accel * t / 12
        else:
            # Intervention effect: growth decelerates
            progress = (t - t_intervention) / (n - t_intervention)
            growth   = growth_pre * (1 - 0.5 * progress) + growth_post * 0.5 * progress
        # Monthly step + seasonal cycle + noise
        monthly_growth = growth / 12.0
        seasonal       = 3.0 * np.sin(2 * np.pi * (t % 12) / 12.0)
        noise          = rng.normal(0, 0.05)
        co2[t]         = co2[t-1] + monthly_growth + noise

    # ── Build ORI-C proxies ────────────────────────────────────────────────────
    def _robust_minmax(x: np.ndarray) -> np.ndarray:
        lo, hi = np.percentile(x, 5), np.percentile(x, 95)
        if hi - lo < 1e-9:
            return np.zeros_like(x)
        return np.clip((x - lo) / (hi - lo), 0, 1)

    # O: 1 - acceleration (positive clip)
    growth_arr = np.diff(co2, prepend=co2[0])
    accel_arr  = np.clip(np.diff(growth_arr, prepend=growth_arr[0]), 0, None)
    O = 1.0 - _robust_minmax(accel_arr)

    # R: 1 - rolling volatility (24-month window)
    roll_std = pd.Series(co2).rolling(24, min_periods=4).std().fillna(0).to_numpy()
    R = 1.0 - _robust_minmax(roll_std)

    # I: seasonal regularity (amplitude of detrended seasonal cycle)
    trend = pd.Series(co2).rolling(13, min_periods=1, center=True).mean().to_numpy()
    detrended = co2 - trend
    amp = pd.Series(np.abs(detrended)).rolling(12, min_periods=4).max().to_numpy()
    I = _robust_minmax(amp)

    # S: cumulative fraction below 360 ppm
    below = (co2 < 360.0).astype(float)
    S = np.cumsum(below) / (np.arange(n) + 1.0)
    S = (S - S.min()) / (S.max() - S.min() + 1e-9)

    # demand: CO₂ excess above 280 ppm pre-industrial
    demand = np.clip((co2 - 280.0) / 280.0, 0, 1)

    return pd.DataFrame({
        "t":       np.arange(n),
        "O":       np.clip(O, 0, 1),
        "R":       np.clip(R, 0, 1),
        "I":       np.clip(I, 0, 1),
        "S":       np.clip(S, 0, 1),
        "demand":  np.clip(demand, 0, 1),
    })


# ── GISTEMP synthetic generator ───────────────────────────────────────────────

def _generate_gistemp(n: int, seed: int) -> pd.DataFrame:
    """Simulate global temperature anomaly series with tipping-point risk.

    Phase 1 (0 → n//3):    Slow warming, system still coupled (I high)
    Phase 2 (n//3 → 2n//3): Accelerated warming, increased volatility
    Phase 3 (2n//3 → end):  Regime shift risk — symbolic saturation test
    """
    rng = np.random.default_rng(seed)

    T = np.zeros(n)
    T[0] = -0.20  # baseline anomaly (1950s)

    for t in range(1, n):
        frac = t / n
        if frac < 1/3:
            drift = 0.008 / 12.0
            noise_sd = 0.04
        elif frac < 2/3:
            drift = 0.018 / 12.0
            noise_sd = 0.07
        else:
            drift = 0.025 / 12.0
            noise_sd = 0.10
        T[t] = T[t-1] + drift + rng.normal(0, noise_sd)

    def _robust_minmax(x: np.ndarray) -> np.ndarray:
        lo, hi = np.percentile(x, 5), np.percentile(x, 95)
        if hi - lo < 1e-9:
            return np.zeros_like(x)
        return np.clip((x - lo) / (hi - lo), 0, 1)

    # O: 1 - positive anomaly
    T_pos = np.clip(T, 0, None)
    O = 1.0 - _robust_minmax(T_pos)

    # R: 1 - 10-year rolling std
    win = min(120, n // 4)
    roll_std = pd.Series(T).rolling(win, min_periods=12).std().fillna(0).to_numpy()
    R = 1.0 - _robust_minmax(roll_std)

    # I: annual cycle coherence (rolling corr at lag 12)
    lag12 = np.concatenate([T[:12], T[:-12]])
    coherence = np.zeros(n)
    wc = min(60, n // 4)
    for i in range(wc, n):
        x = T[i-wc:i]
        y = lag12[i-wc:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coherence[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(coherence, 0, None))

    # S: cumulative fraction below +1°C
    below = (T < 1.0).astype(float)
    S = np.cumsum(below) / (np.arange(n) + 1.0)
    S = (S - S.min()) / (S.max() - S.min() + 1e-9)

    # demand: positive anomaly normalised
    demand = _robust_minmax(T_pos)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
    })


# ── proxy_spec.json ───────────────────────────────────────────────────────────

def _proxy_spec(dataset_id: str) -> dict:
    roles = ["O", "R", "I", "demand", "S"]
    return {
        "dataset_id":   dataset_id,
        "spec_version": "2.1",
        "sector":       "climate",
        "time_column":  "t",
        "time_mode":    "index",
        "columns": [
            {
                "source_column": r,
                "oric_role": r,
                "oric_variable": r,
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": f"{r} proxy for climate sector.",
                "manipulability_note": "Physical or cumulative construct."
            }
            for r in roles
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def generate(outdir: Path, seed: int, pilot_id: str, n: int = 300) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "co2_mauna_loa":
        df = _generate_co2(n, seed)
        spec = _proxy_spec("sector_climate.pilot_co2_mauna_loa.synth.v1")
    elif pilot_id == "gistemp":
        df = _generate_gistemp(n, seed)
        spec = _proxy_spec("sector_climate.pilot_gistemp.synth.v1")
    else:
        raise ValueError(f"Unknown pilot_id: {pilot_id!r}")

    df.to_csv(outdir / "real.csv", index=False)
    (outdir / "proxy_spec.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False)
    )


# ── CLI (standalone) ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True,
                        choices=["co2_mauna_loa", "gistemp"])
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=300)
    args = parser.parse_args()
    generate(args.outdir, args.seed, args.pilot, args.n)
    print(f"Generated {args.n} rows for pilot={args.pilot} → {args.outdir}")
