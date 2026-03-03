"""fetch_real_data.py — Finance sector real-data fetcher.

Sources (all public, no authentication required):

  sp500 — S&P 500 monthly OHLCV via stooq.com (public, no key needed)
    URL: https://stooq.com/q/d/l/?s=%5Espx&i=m
    Columns: Date, Open, High, Low, Close, Volume
    Period: ~1950 → present, monthly

  btc — Bitcoin monthly price via CoinGecko public API
    URL: https://api.coingecko.com/api/v3/coins/bitcoin/market_chart
         ?vs_currency=usd&days=max&interval=monthly
    Period: 2013-04 → present, monthly

Output (per pilot):
  03_Data/sector_finance/real/pilot_<id>/raw/       ← raw downloaded files
  03_Data/sector_finance/real/pilot_<id>/real.csv   ← normalised ORI-C format
  03_Data/sector_finance/real/pilot_<id>/fetch_manifest.json

ORI-C mapping (sp500):
  O = market_breadth_proxy (rolling % months closing above 10-month MA)
  R = 1 − drawdown_norm             (resilience: inverse of max drawdown depth)
  I = price_volume_coherence_norm   (integration: rolling corr price × volume)
  S = cumulative_momentum_norm      (symbolic stock: cumulative positive returns)
  demand = realised_volatility_norm (external pressure = market fear / uncertainty)

ORI-C mapping (btc):
  O = 1 − drawdown_from_ATH_norm    (network organisation capacity)
  R = 1 − rolling_volatility_norm   (resilience: inverse of 6-month volatility)
  I = log_volume_coherence_norm     (market integration)
  S = hodl_proxy_cumul_norm         (symbolic stock: long-term holder momentum)
  demand = realised_volatility_norm (fear/greed pressure)
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "shared"))
from fetch_utils import (
    download_bytes, robust_minmax, minmax, cumsum_norm,
    rolling_corr, save_real_csv, write_manifest, sha256_bytes,
)

REPO_ROOT = _HERE.parent.parent.parent

# ── URLs ──────────────────────────────────────────────────────────────────────

_SPX_URL = "https://stooq.com/q/d/l/?s=%5Espx&i=m"
_BTC_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=max&interval=monthly"
)


# ── S&P 500 ───────────────────────────────────────────────────────────────────

def _fetch_sp500(outdir: Path, raw_dir: Path) -> tuple[pd.DataFrame, bytes]:
    """Download and parse S&P 500 monthly from stooq."""
    raw = download_bytes(_SPX_URL)
    (raw_dir / "spx_monthly.csv").write_bytes(raw)

    df = pd.read_csv(io.StringIO(raw.decode("utf-8", errors="replace")))
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Keep 1960+ for enough data
    df = df[df["date"].dt.year >= 1960].reset_index(drop=True)
    return df, raw


def _build_sp500_oric(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    close = df["close"].to_numpy(dtype=float)
    volume = df.get("volume", pd.Series(np.ones(n))).to_numpy(dtype=float)

    # ── O: market breadth — rolling % months above 10-month MA ───────────────
    ma10 = pd.Series(close).rolling(10, min_periods=2).mean().to_numpy()
    above_ma = (close > ma10).astype(float)
    breadth = pd.Series(above_ma).rolling(12, min_periods=3).mean().to_numpy()
    O = robust_minmax(breadth)

    # ── R: resilience = 1 − rolling max drawdown ─────────────────────────────
    rolling_max = pd.Series(close).cummax().to_numpy()
    drawdown = (rolling_max - close) / (rolling_max + 1e-9)
    dd_smooth = pd.Series(drawdown).rolling(12, min_periods=2).mean().to_numpy()
    R = 1.0 - robust_minmax(dd_smooth)

    # ── I: price-volume coherence ─────────────────────────────────────────────
    log_ret = np.diff(np.log(np.clip(close, 1e-9, None)), prepend=0.0)
    vol_norm = robust_minmax(np.log1p(np.clip(volume, 0, None)))
    coh = rolling_corr(log_ret, vol_norm, window=24)
    I = robust_minmax(np.clip(coh, 0, None))

    # ── S: cumulative momentum stock ──────────────────────────────────────────
    log_ret_pos = np.clip(log_ret, 0, None)
    S = cumsum_norm(log_ret_pos)

    # ── demand: realised 6-month volatility ───────────────────────────────────
    rvol = pd.Series(log_ret).rolling(6, min_periods=2).std().fillna(0).to_numpy()
    demand = robust_minmax(rvol)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
        "date":   df["date"].dt.strftime("%Y-%m"),
        "close":  close,
    })


# ── Bitcoin ───────────────────────────────────────────────────────────────────

def _fetch_btc(outdir: Path, raw_dir: Path) -> tuple[pd.DataFrame, bytes]:
    """Download and parse Bitcoin monthly from CoinGecko."""
    raw = download_bytes(_BTC_URL)
    (raw_dir / "btc_monthly.json").write_bytes(raw)

    data = json.loads(raw.decode("utf-8"))
    prices  = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    df_price = pd.DataFrame(prices, columns=["ts_ms", "price"])
    df_vol   = pd.DataFrame(volumes, columns=["ts_ms", "volume"])

    df = df_price.merge(df_vol, on="ts_ms", how="left")
    df["date"] = pd.to_datetime(df["ts_ms"], unit="ms")
    df = df.sort_values("date").reset_index(drop=True)

    # Keep 2014+ for cleaner data
    df = df[df["date"].dt.year >= 2014].reset_index(drop=True)
    return df, raw


def _build_btc_oric(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    price  = df["price"].to_numpy(dtype=float)
    volume = df["volume"].fillna(0).to_numpy(dtype=float)

    # ── O: 1 − drawdown from all-time high ───────────────────────────────────
    ath = pd.Series(price).cummax().to_numpy()
    drawdown = (ath - price) / (ath + 1e-9)
    O = 1.0 - robust_minmax(drawdown)

    # ── R: 1 − 6-month rolling volatility ────────────────────────────────────
    log_ret = np.diff(np.log(np.clip(price, 1e-9, None)), prepend=0.0)
    rvol = pd.Series(log_ret).rolling(6, min_periods=2).std().fillna(0).to_numpy()
    R = 1.0 - robust_minmax(rvol)

    # ── I: log-volume coherence with price momentum ────────────────────────────
    log_vol = np.log1p(np.clip(volume, 0, None))
    coh = rolling_corr(np.abs(log_ret), robust_minmax(log_vol), window=12)
    I = robust_minmax(np.clip(coh, 0, None))

    # ── S: HODL proxy = cumulative positive return months ─────────────────────
    positive_months = (log_ret > 0).astype(float)
    S = cumsum_norm(positive_months)

    # ── demand: realised 6-month volatility ───────────────────────────────────
    demand = robust_minmax(rvol)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
        "date":   df["date"].dt.strftime("%Y-%m"),
        "price_usd": price,
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
                "fragility_note": f"{r} proxy for finance sector.",
                "manipulability_note": "Market data; aggregated across many participants."
            }
            for r in ["O", "R", "I", "demand", "S"]
        ],
    }


# ── Main CLI ──────────────────────────────────────────────────────────────────

def run(pilot_id: str, outdir: Path, repo_root: Path) -> None:
    outdir = outdir.resolve()
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "sp500":
        df_raw, raw_bytes = _fetch_sp500(outdir, raw_dir)
        df_oric = _build_sp500_oric(df_raw)
        spec = _proxy_spec("sector_finance.pilot_sp500.real.v1")
    elif pilot_id == "btc":
        df_raw, raw_bytes = _fetch_btc(outdir, raw_dir)
        df_oric = _build_btc_oric(df_raw)
        spec = _proxy_spec("sector_finance.pilot_btc.real.v1")
    else:
        print(f"Unknown pilot_id: {pilot_id}", file=sys.stderr)
        sys.exit(1)

    save_real_csv(df_oric, outdir / "real.csv")
    (outdir / "proxy_spec.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False)
    )
    write_manifest(
        outdir / "fetch_manifest.json",
        pilot_id=pilot_id,
        sector="finance",
        n_rows=len(df_oric),
        sha256=sha256_bytes(raw_bytes) if isinstance(raw_bytes, bytes) else "n/a",
    )
    print(f"[finance/{pilot_id}] Saved {len(df_oric)} rows to {outdir/'real.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch finance real data")
    parser.add_argument("--pilot-id", required=True,
                        choices=["sp500", "btc"],
                        help="Pilot to fetch")
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    run(args.pilot_id, args.outdir, REPO_ROOT)


if __name__ == "__main__":
    main()
