"""generate_synth.py — Synthetic data generator for the Finance sector panel.

Two pilots:

  sp500 : Equity market cycle with bull/bear regime transition
  btc   : Crypto market with euphoria auto-reinforcement (bull run + crash)

ORI-C mappings:

  sp500:
    O(t) = market_breadth_proxy     (% stocks above moving average)
    R(t) = 1 − drawdown_norm         (resilience: inverse drawdown)
    I(t) = price_volume_coherence    (market integration)
    S(t) = cumulative_momentum       (symbolic stock: investor confidence)
    demand(t) = realised_volatility  (fear/uncertainty)

  btc:
    O(t) = 1 − drawdown_from_ATH     (network organisation)
    R(t) = 1 − rolling_volatility    (resilience)
    I(t) = volume_coherence          (market integration)
    S(t) = hodl_proxy                (symbolic stock: HODL conviction)
    demand(t) = realised_volatility  (fear/greed)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _robust_minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(x, 5), np.percentile(x, 95)
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0, 1)


def _cumsum_norm(x: np.ndarray) -> np.ndarray:
    cs = np.cumsum(x)
    mx = cs.max()
    return cs / mx if mx > 1e-9 else np.zeros_like(cs)


# ── S&P 500 synthetic ─────────────────────────────────────────────────────────

def _generate_sp500(n: int, seed: int) -> pd.DataFrame:
    """Equity market with 3 regimes:
    - Bull market (0 → n//3): gradual rally, low vol, breadth expands
    - Correction/Bear (n//3 → 2n//3): drawdown, high vol, breadth contracts
    - Recovery + symbolic threshold crossing (2n//3 → end): regime restoration
    """
    rng = np.random.default_rng(seed)

    close = np.zeros(n)
    close[0] = 1000.0
    volume = np.zeros(n)
    volume[0] = 1.0

    t_bear = n // 3
    t_recov = 2 * n // 3

    for t in range(1, n):
        frac = t / n
        if t < t_bear:
            drift = 0.008 + 0.002 * frac   # bull: accelerating
            vol   = 0.03
            v_trend = 1.0 + 0.5 * frac
        elif t < t_recov:
            drift = -0.015 + 0.005 * (t - t_bear) / (t_recov - t_bear)
            vol   = 0.06 + 0.02 * rng.random()
            v_trend = 1.5 - 0.5 * (t - t_bear) / (t_recov - t_bear)
        else:
            progress = (t - t_recov) / (n - t_recov)
            drift = 0.006 + 0.005 * progress
            vol   = 0.035 - 0.01 * progress
            v_trend = 1.0 + progress

        ret = rng.normal(drift, vol)
        close[t] = max(close[t-1] * (1 + ret), 10.0)
        volume[t] = max(v_trend + rng.normal(0, 0.2), 0.1)

    log_ret = np.diff(np.log(close), prepend=0.0)
    ma10 = pd.Series(close).rolling(10, min_periods=2).mean().to_numpy()
    above_ma = (close > ma10).astype(float)
    breadth = pd.Series(above_ma).rolling(12, min_periods=3).mean().to_numpy()
    O = _robust_minmax(breadth)

    rolling_max = pd.Series(close).cummax().to_numpy()
    drawdown = (rolling_max - close) / (rolling_max + 1e-9)
    dd_smooth = pd.Series(drawdown).rolling(12, min_periods=2).mean().to_numpy()
    R = 1.0 - _robust_minmax(dd_smooth)

    vol_norm = _robust_minmax(np.log1p(volume))
    coh = np.zeros(n)
    w = 24
    for i in range(w, n):
        x, y = log_ret[i-w:i], vol_norm[i-w:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coh[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(coh, 0, None))

    S = _cumsum_norm(np.clip(log_ret, 0, None))

    rvol = pd.Series(log_ret).rolling(6, min_periods=2).std().fillna(0).to_numpy()
    demand = _robust_minmax(rvol)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
    })


# ── Bitcoin synthetic ──────────────────────────────────────────────────────────

def _generate_btc(n: int, seed: int) -> pd.DataFrame:
    """Bitcoin-like series with euphoria auto-reinforcement then crash:
    - Accumulation (0 → n//4): slow rise, moderate vol
    - Bull run (n//4 → n//2): explosive rally, self-reinforcing S(t)
    - Blow-off top + crash (n//2 → 3n//4): crash, extreme vol
    - Recovery (3n//4 → end): gradual rebuild of symbolic stock
    """
    rng = np.random.default_rng(seed)

    price = np.zeros(n)
    price[0] = 100.0
    volume = np.zeros(n)
    volume[0] = 1.0

    t_bull  = n // 4
    t_crash = n // 2
    t_recov = 3 * n // 4

    for t in range(1, n):
        if t < t_bull:
            drift, vol, vf = 0.010, 0.08, 1.0
        elif t < t_crash:
            # Euphoria: accelerating drift
            progress = (t - t_bull) / (t_crash - t_bull)
            drift = 0.03 + 0.05 * progress
            vol   = 0.12 + 0.08 * progress
            vf    = 2.0 + 3.0 * progress
        elif t < t_recov:
            progress = (t - t_crash) / (t_recov - t_crash)
            drift = -0.04 + 0.02 * progress
            vol   = 0.20 - 0.08 * progress
            vf    = 4.0 - 2.0 * progress
        else:
            progress = (t - t_recov) / (n - t_recov)
            drift = 0.008 + 0.01 * progress
            vol   = 0.12 - 0.04 * progress
            vf    = 2.0 + 1.0 * progress

        ret = rng.normal(drift, vol)
        price[t]  = max(price[t-1] * (1 + ret), 0.01)
        volume[t] = max(vf + rng.normal(0, 0.3), 0.1)

    log_ret = np.diff(np.log(price), prepend=0.0)
    ath = pd.Series(price).cummax().to_numpy()
    drawdown = (ath - price) / (ath + 1e-9)
    O = 1.0 - _robust_minmax(drawdown)

    rvol = pd.Series(log_ret).rolling(6, min_periods=2).std().fillna(0).to_numpy()
    R = 1.0 - _robust_minmax(rvol)

    log_vol = np.log1p(volume)
    coh = np.zeros(n)
    w = 12
    for i in range(w, n):
        x, y = np.abs(log_ret[i-w:i]), log_vol[i-w:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coh[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(coh, 0, None))

    S = _cumsum_norm((log_ret > 0).astype(float))
    demand = _robust_minmax(rvol)

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
    return {
        "dataset_id":   dataset_id,
        "spec_version": "2.1",
        "sector":       "finance",
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
                "fragility_note": f"{r} finance proxy.",
                "manipulability_note": "Aggregated market data."
            }
            for r in ["O", "R", "I", "demand", "S"]
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def generate(outdir: Path, seed: int, pilot_id: str, n: int = 250) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "sp500":
        df = _generate_sp500(n, seed)
        spec = _proxy_spec("sector_finance.pilot_sp500.synth.v1")
    elif pilot_id == "btc":
        df = _generate_btc(n, seed)
        spec = _proxy_spec("sector_finance.pilot_btc.synth.v1")
    else:
        raise ValueError(f"Unknown pilot_id: {pilot_id!r}")

    df.to_csv(outdir / "real.csv", index=False)
    (outdir / "proxy_spec.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True, choices=["sp500", "btc"])
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=250)
    args = parser.parse_args()
    generate(args.outdir, args.seed, args.pilot, args.n)
    print(f"Generated {args.n} rows for pilot={args.pilot} → {args.outdir}")
