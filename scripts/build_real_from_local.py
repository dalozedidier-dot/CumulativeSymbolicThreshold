"""build_real_from_local.py — Process locally downloaded data files into ORI-C real.csv.

Reads from:
  data/climate/co2_mm_mlo.csv       → NOAA Mauna Loa CO₂ (1958–present)
  data/climate/GLB.Ts+dSST.csv      → NASA GISTEMP v4 global mean anomalies
  data/finance/^spx_m.csv           → S&P 500 monthly (stooq format)

Writes to:
  03_Data/sector_climate/real/pilot_co2_mauna_loa/real.csv
  03_Data/sector_climate/real/pilot_gistemp/real.csv
  03_Data/sector_finance/real/pilot_sp500/real.csv

ORI-C variable mapping follows proxy_spec.json v2.1 definitions.
Run from repo root:
  python scripts/build_real_from_local.py
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── Normalisation helpers (numpy-native, no pd.Series.quantile dependency) ────

def _robust_minmax(arr: np.ndarray, q_lo: float = 0.02, q_hi: float = 0.98) -> np.ndarray:
    a = arr.astype(float)
    valid = a[~np.isnan(a)]
    if len(valid) == 0:
        return np.zeros_like(a)
    lo = float(np.quantile(valid, q_lo))
    hi = float(np.quantile(valid, q_hi))
    if hi <= lo:
        return np.zeros_like(a)
    out = np.clip((a - lo) / (hi - lo), 0.0, 1.0)
    # Fill NaN positions with 0
    out = np.where(np.isnan(out), 0.0, out)
    return out


def _minmax(arr: np.ndarray) -> np.ndarray:
    a = arr.astype(float)
    valid = a[~np.isnan(a)]
    if len(valid) == 0:
        return np.zeros_like(a)
    lo, hi = float(valid.min()), float(valid.max())
    if hi <= lo:
        return np.zeros_like(a)
    out = np.clip((a - lo) / (hi - lo), 0.0, 1.0)
    out = np.where(np.isnan(out), 0.0, out)
    return out


def _rolling_corr(a: np.ndarray, b: np.ndarray, window: int = 24) -> np.ndarray:
    """Rolling Pearson correlation (absolute value)."""
    n = len(a)
    out = np.zeros(n)
    for i in range(window, n + 1):
        xa = a[i - window:i]
        xb = b[i - window:i]
        if xa.std() > 1e-10 and xb.std() > 1e-10:
            out[i - 1] = abs(float(np.corrcoef(xa, xb)[0, 1]))
    # Back-fill leading zeros
    first_nonzero = np.argmax(out > 0)
    if first_nonzero > 0:
        out[:first_nonzero] = out[first_nonzero] if out[first_nonzero] > 0 else 0.0
    return np.clip(out, 0.0, 1.0)


def _cumsum_decay(arr: np.ndarray, decay: float = 0.005) -> np.ndarray:
    """Cumulative sum with exponential decay → normalised [0,1]."""
    out = np.zeros(len(arr))
    for t in range(1, len(arr)):
        out[t] = out[t - 1] * (1 - decay) + arr[t]
    return _robust_minmax(out)


def _save_real_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  [save] {path}  ({len(df)} rows × {len(df.columns)} cols)")


def _write_manifest(path: Path, *, sector: str, pilot: str, n_rows: int,
                    date_range: tuple[str, str], source_file: str) -> None:
    manifest = {
        "sector":       sector,
        "pilot":        pilot,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "n_rows":       n_rows,
        "date_range":   {"start": date_range[0], "end": date_range[1]},
        "source":       source_file,
        "method":       "build_real_from_local.py",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"  [manifest] → {path}")


# ── CO₂ Mauna Loa ─────────────────────────────────────────────────────────────

def process_co2(repo_root: Path) -> None:
    src = repo_root / "data" / "climate" / "co2_mm_mlo.csv"
    outdir = repo_root / "03_Data" / "sector_climate" / "real" / "pilot_co2_mauna_loa"
    print(f"\n[co2_mauna_loa] Reading {src}")

    # Skip NOAA comment lines (start with #)
    with open(src, encoding="utf-8") as f:
        content = f.read()
    lines = [l for l in content.splitlines()
             if not l.strip().startswith("#") and l.strip()]
    text = "\n".join(lines)

    # Actual NOAA column names: year,month,decimal date,average,deseasonalized,ndays,sdev,unc
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]

    # Build date column
    df["date"] = pd.to_datetime(
        df["year"].astype(int).astype(str) + "-" +
        df["month"].astype(int).astype(str).str.zfill(2) + "-01"
    )
    df = df.sort_values("date").reset_index(drop=True)

    # The 'average' column is the monthly mean CO₂; no -99.99 missing in this file
    # Filter to 1965+ for clean 60-year series
    df = df[df["year"] >= 1965].reset_index(drop=True)
    co2 = df["average"].to_numpy(dtype=float)
    n = len(co2)

    # ── O: inverse CO₂ monthly acceleration ─────────────────────────────────
    growth = np.diff(co2, prepend=co2[0])
    accel = np.diff(growth, prepend=growth[0])
    accel_pos = np.clip(accel, 0, None)
    O = 1.0 - _robust_minmax(accel_pos)

    # ── R: climate resilience = inverse 24-month rolling std ─────────────────
    roll_std = pd.Series(co2).rolling(24, min_periods=4).std().fillna(0).to_numpy()
    R = 1.0 - _robust_minmax(roll_std)

    # ── I: system integration = seasonal regularity ───────────────────────────
    detrended = co2 - pd.Series(co2).rolling(13, min_periods=1, center=True).mean().to_numpy()
    seasonal_amp = pd.Series(np.abs(detrended)).rolling(12, min_periods=4).max().to_numpy()
    I = _robust_minmax(seasonal_amp)

    # ── S: symbolic safety stock = cumulative fraction below 380 ppm ─────────
    below = (co2 < 380.0).astype(float)
    S = np.cumsum(below) / (np.arange(n) + 1.0)
    S = _minmax(S)

    # ── demand: CO₂ excess above pre-industrial baseline ─────────────────────
    demand = np.clip((co2 - 280.0) / (560.0 - 280.0), 0.0, 1.0)

    out_df = pd.DataFrame({
        "t":       np.arange(n),
        "O":       np.clip(O, 0, 1),
        "R":       np.clip(R, 0, 1),
        "I":       np.clip(I, 0, 1),
        "S":       np.clip(S, 0, 1),
        "demand":  np.clip(demand, 0, 1),
        "date":    df["date"].dt.strftime("%Y-%m"),
        "co2_ppm": co2,
    })

    _save_real_csv(out_df, outdir / "real.csv")
    _write_manifest(
        outdir / "fetch_manifest.json",
        sector="climate", pilot="co2_mauna_loa", n_rows=n,
        date_range=(out_df["date"].iloc[0], out_df["date"].iloc[-1]),
        source_file="data/climate/co2_mm_mlo.csv",
    )
    print(f"  [co2_mauna_loa] {n} months from {out_df['date'].iloc[0]} to {out_df['date'].iloc[-1]}")
    print(f"  CO₂ range: {co2.min():.1f} – {co2.max():.1f} ppm")


# ── GISTEMP ───────────────────────────────────────────────────────────────────

def process_gistemp(repo_root: Path) -> None:
    src = repo_root / "data" / "climate" / "GLB.Ts+dSST.csv"
    outdir = repo_root / "03_Data" / "sector_climate" / "real" / "pilot_gistemp"
    print(f"\n[gistemp] Reading {src}")

    with open(src, encoding="utf-8") as f:
        content = f.read()

    # Skip first line "Land-Ocean: Global Means"
    lines = content.splitlines()
    clean_lines = [l for l in lines if not l.startswith("Land-Ocean")]
    text_clean = "\n".join(clean_lines)

    df = pd.read_csv(io.StringIO(text_clean))
    month_cols = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    existing = [c for c in month_cols if c in df.columns]

    # Replace *** with NaN and convert to numeric
    for c in existing:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace("***", "", regex=False),
            errors="coerce"
        )

    # Melt to long format
    df_long = df[["Year"] + existing].melt(
        id_vars="Year", var_name="month_name", value_name="anomaly_raw"
    )
    month_map = {m: i + 1 for i, m in enumerate(month_cols)}
    df_long["month"] = df_long["month_name"].map(month_map)
    df_long = df_long.dropna(subset=["anomaly_raw"]).copy()

    # GISTEMP v4: values are directly in °C (confirmed from recent year values)
    df_long["anomaly"] = df_long["anomaly_raw"].astype(float)

    df_long["date"] = pd.to_datetime(
        df_long["Year"].astype(int).astype(str) + "-" +
        df_long["month"].astype(int).astype(str).str.zfill(2) + "-01"
    )
    df_long = df_long.sort_values("date").reset_index(drop=True)

    # Filter to 1950+ (enough modern data, >900 months)
    df_long = df_long[df_long["Year"] >= 1950].reset_index(drop=True)
    T = df_long["anomaly"].to_numpy(dtype=float)
    n = len(T)

    # ── O: inverse positive temperature anomaly ──────────────────────────────
    T_pos = np.clip(T, 0, None)
    O = 1.0 - _robust_minmax(T_pos)

    # ── R: inverse 10-year rolling std (120 months) ──────────────────────────
    roll_std = pd.Series(T).rolling(120, min_periods=12).std().fillna(0).to_numpy()
    R = 1.0 - _robust_minmax(roll_std)

    # ── I: annual cycle coherence (rolling corr with lag-12) ─────────────────
    lag12 = np.concatenate([T[:12], T[:-12]])
    coherence = np.zeros(n)
    win = 60
    for i in range(win, n):
        x = T[i - win:i]
        y = lag12[i - win:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coherence[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(coherence, 0, None))

    # ── S: symbolic stock = cumulative fraction below +1°C threshold ─────────
    below = (T < 1.0).astype(float)
    S = np.cumsum(below) / (np.arange(n) + 1.0)
    S = _minmax(S)

    # ── demand: normalised positive anomaly ───────────────────────────────────
    demand = _robust_minmax(T_pos)

    out_df = pd.DataFrame({
        "t":           np.arange(n),
        "O":           np.clip(O, 0, 1),
        "R":           np.clip(R, 0, 1),
        "I":           np.clip(I, 0, 1),
        "S":           np.clip(S, 0, 1),
        "demand":      np.clip(demand, 0, 1),
        "date":        df_long["date"].dt.strftime("%Y-%m"),
        "T_anomaly_C": T,
    })

    _save_real_csv(out_df, outdir / "real.csv")
    _write_manifest(
        outdir / "fetch_manifest.json",
        sector="climate", pilot="gistemp", n_rows=n,
        date_range=(out_df["date"].iloc[0], out_df["date"].iloc[-1]),
        source_file="data/climate/GLB.Ts+dSST.csv",
    )
    print(f"  [gistemp] {n} months from {out_df['date'].iloc[0]} to {out_df['date'].iloc[-1]}")
    print(f"  Anomaly range: {T.min():.3f} – {T.max():.3f} °C")


# ── S&P 500 ───────────────────────────────────────────────────────────────────

def process_sp500(repo_root: Path) -> None:
    src = repo_root / "data" / "finance" / "^spx_m.csv"
    outdir = repo_root / "03_Data" / "sector_finance" / "real" / "pilot_sp500"
    print(f"\n[sp500] Reading {src}")

    df = pd.read_csv(src)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Filter to 1960+ for sufficient modern data
    df = df[df["date"].dt.year >= 1960].reset_index(drop=True)
    n = len(df)
    close = df["close"].to_numpy(dtype=float)
    volume = df["volume"].fillna(0).to_numpy(dtype=float)

    # ── O: market breadth — rolling % months above 10-month MA ───────────────
    ma10 = pd.Series(close).rolling(10, min_periods=2).mean().to_numpy()
    above_ma = (close > ma10).astype(float)
    breadth = pd.Series(above_ma).rolling(12, min_periods=3).mean().fillna(0).to_numpy()
    O = _robust_minmax(breadth)

    # ── R: resilience = 1 − rolling max drawdown ─────────────────────────────
    rolling_max = pd.Series(close).cummax().to_numpy()
    drawdown = (rolling_max - close) / (rolling_max + 1e-9)
    dd_smooth = pd.Series(drawdown).rolling(12, min_periods=2).mean().to_numpy()
    R = 1.0 - _robust_minmax(dd_smooth)

    # ── I: price-volume coherence ─────────────────────────────────────────────
    log_ret = np.diff(np.log(np.clip(close, 1e-9, None)), prepend=0.0)
    # Volume is zero for very early data; use log1p, then normalise
    vol_norm = _robust_minmax(np.log1p(np.clip(volume, 0, None)))
    I_raw = _rolling_corr(log_ret, vol_norm, window=24)
    I = _robust_minmax(I_raw)

    # ── S: cumulative momentum stock ──────────────────────────────────────────
    log_ret_pos = np.clip(log_ret, 0, None)
    S = _cumsum_decay(log_ret_pos)

    # ── demand: realised 6-month volatility ───────────────────────────────────
    rvol = pd.Series(log_ret).rolling(6, min_periods=2).std().fillna(0).to_numpy()
    demand = _robust_minmax(rvol)

    out_df = pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
        "date":   df["date"].dt.strftime("%Y-%m"),
        "close":  close,
    })

    _save_real_csv(out_df, outdir / "real.csv")
    _write_manifest(
        outdir / "fetch_manifest.json",
        sector="finance", pilot="sp500", n_rows=n,
        date_range=(out_df["date"].iloc[0], out_df["date"].iloc[-1]),
        source_file="data/finance/^spx_m.csv",
    )
    print(f"  [sp500] {n} months from {out_df['date'].iloc[0]} to {out_df['date'].iloc[-1]}")
    print(f"  Close range: {close.min():.2f} – {close.max():.2f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Build real.csv from local data files")
    parser.add_argument(
        "--pilots", nargs="+",
        choices=["co2_mauna_loa", "gistemp", "sp500", "all"],
        default=["all"],
        help="Pilots to process (default: all)",
    )
    args = parser.parse_args()
    pilots = args.pilots
    if "all" in pilots:
        pilots = ["co2_mauna_loa", "gistemp", "sp500"]

    for pilot in pilots:
        if pilot == "co2_mauna_loa":
            process_co2(REPO_ROOT)
        elif pilot == "gistemp":
            process_gistemp(REPO_ROOT)
        elif pilot == "sp500":
            process_sp500(REPO_ROOT)

    print("\n[build_real_from_local] Done.")


if __name__ == "__main__":
    main()
