"""fetch_real_data.py — Climate sector real-data fetcher.

Sources (all public, no authentication required):

  co2_mauna_loa — NOAA ESRL Mauna Loa monthly CO₂ (1958–present)
    URL: https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv
    Columns used: year, month, decimal_date, average, interpolated, trend, days
    Period: 1960-01 → present, monthly

  gistemp — NASA GISS Surface Temperature Analysis (GISTEMP v4), global mean
    URL: https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv
    Columns used: Year + monthly anomalies (J-D annual mean)
    Period: 1880 → present, annual (resampled to monthly for ORI-C)

Output (per pilot):
  03_Data/sector_climate/real/pilot_<id>/raw/       ← raw downloaded files
  03_Data/sector_climate/real/pilot_<id>/real.csv   ← normalised ORI-C format
  03_Data/sector_climate/real/pilot_<id>/fetch_manifest.json

ORI-C mapping (co2_mauna_loa):
  O = 1 − CO₂_acceleration_norm   → ecosystem org capacity (low accel = better managed)
  R = 1 − rolling_volatility_norm  → climate resilience (stable = resilient)
  I = seasonal_regularity_norm     → system integration (regular season = coupled system)
  S = fraction_below_350ppm_cumul  → symbolic safety stock
  demand = (CO₂_ppm − 280) / (560 − 280)  → CO₂ excess above pre-industrial

ORI-C mapping (gistemp):
  O = 1 − T_anomaly_pos_norm       → ecosystem capacity below critical threshold
  R = 1 − rolling10y_std_norm      → temperature stability / resilience
  I = land_ocean_coherence_norm    → system integration (hemispheric coupling proxy)
  S = fraction_below_1C_cumul      → symbolic stock: fraction of history under +1°C
  demand = T_anomaly_pos_norm      → temperature pressure
"""
from __future__ import annotations

import argparse
import io
import json
import sys
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

_CO2_URL = (
    "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
)
_GISTEMP_URL = (
    "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
)


# ── CO₂ Mauna Loa ─────────────────────────────────────────────────────────────

def _fetch_co2(outdir: Path, raw_dir: Path) -> tuple[pd.DataFrame, bytes]:
    """Download and parse NOAA Mauna Loa monthly CO₂."""
    raw = download_bytes(_CO2_URL)
    (raw_dir / "co2_mm_mlo.csv").write_bytes(raw)

    # Skip comment lines starting with #
    lines = raw.decode("utf-8", errors="replace").splitlines()
    data_lines = [l for l in lines if not l.strip().startswith("#") and l.strip()]
    text = "\n".join(data_lines)

    df = pd.read_csv(
        io.StringIO(text),
        header=None,
        names=["year", "month", "decimal_date", "average", "interpolated",
               "trend", "days"],
        na_values=["-99.99", "-9.99", "-1"],
    )
    df = df.dropna(subset=["average"]).copy()
    df["date"] = pd.to_datetime(
        df["year"].astype(int).astype(str) + "-" +
        df["month"].astype(int).astype(str).str.zfill(2) + "-01"
    )
    df = df.sort_values("date").reset_index(drop=True)

    # Use interpolated where average is missing
    df["co2"] = df["average"].where(df["average"] > 0, df["interpolated"])
    df = df[df["co2"] > 0].copy()

    # Filter to 1965+ for clean series (≥50 years)
    df = df[df["year"] >= 1965].reset_index(drop=True)

    return df, raw


def _build_co2_oric(df: pd.DataFrame) -> pd.DataFrame:
    """Build ORI-C columns from CO₂ series."""
    n = len(df)
    co2 = df["co2"].to_numpy(dtype=float)

    # ── O: ecosystem organisation = inverse CO₂ monthly acceleration ─────────
    # acceleration = 2nd derivative (month-to-month change in growth rate)
    growth = np.diff(co2, prepend=co2[0])
    accel  = np.diff(growth, prepend=growth[0])
    accel_pos = np.clip(accel, 0, None)  # only positive acceleration is bad
    O = 1.0 - robust_minmax(accel_pos)

    # ── R: climate resilience = inverse of 24-month rolling std ──────────────
    window = 24
    roll_std = pd.Series(co2).rolling(window, min_periods=4).std().fillna(0).to_numpy()
    R = 1.0 - robust_minmax(roll_std)

    # ── I: system integration = seasonal regularity ───────────────────────────
    # Compute the seasonal cycle amplitude per year; regularity = inverse CV
    # Use detrended signal to isolate seasonality
    detrended = co2 - pd.Series(co2).rolling(13, min_periods=1, center=True).mean().to_numpy()
    seasonal_amp = pd.Series(np.abs(detrended)).rolling(12, min_periods=4).max().to_numpy()
    I = robust_minmax(seasonal_amp)  # larger amplitude → stronger coupling

    # ── S: symbolic safety stock = cumulative fraction below 380 ppm ─────────
    threshold_ppm = 380.0  # Kyoto-era concern level
    below = (co2 < threshold_ppm).astype(float)
    S = np.cumsum(below) / (np.arange(n) + 1.0)
    S = minmax(S)

    # ── demand: CO₂ excess above pre-industrial baseline ─────────────────────
    pre_industrial = 280.0
    doubling_ppm   = 560.0  # 2× pre-industrial
    demand = np.clip((co2 - pre_industrial) / (doubling_ppm - pre_industrial), 0.0, 1.0)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
        "date":   df["date"].dt.strftime("%Y-%m"),
        "co2_ppm": co2,
    })


# ── GISTEMP ───────────────────────────────────────────────────────────────────

def _fetch_gistemp(outdir: Path, raw_dir: Path) -> tuple[pd.DataFrame, bytes]:
    """Download and parse NASA GISS surface temperature anomalies."""
    raw = download_bytes(_GISTEMP_URL)
    (raw_dir / "GLB.Ts+dSST.csv").write_bytes(raw)

    text = raw.decode("utf-8", errors="replace")
    # NASA GISS CSV: first row is header, values in tenths of degree (×0.01 °C since v4)
    # Skip description lines starting with "GLOBAL"
    lines = [l for l in text.splitlines() if not l.startswith("GLOBAL") and l.strip()]
    text_clean = "\n".join(lines)

    df = pd.read_csv(io.StringIO(text_clean))

    # Columns: Year, Jan, Feb, ..., Dec, J-D, D-N, DJF, MAM, JJA, SON
    month_cols = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    existing = [c for c in month_cols if c in df.columns]

    # Replace *** (missing) with NaN
    for c in existing + (["J-D"] if "J-D" in df.columns else []):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace("***", ""), errors="coerce")

    # Melt to monthly rows
    df_long = df[["Year"] + existing].melt(id_vars="Year", var_name="month_name", value_name="anomaly_raw")
    month_map = {m: i+1 for i, m in enumerate(month_cols)}
    df_long["month"] = df_long["month_name"].map(month_map)
    df_long = df_long.dropna(subset=["anomaly_raw"]).copy()
    df_long["anomaly"] = df_long["anomaly_raw"] / 100.0  # convert to °C
    df_long["date"] = pd.to_datetime(
        df_long["Year"].astype(int).astype(str) + "-" +
        df_long["month"].astype(int).astype(str).str.zfill(2) + "-01"
    )
    df_long = df_long.sort_values("date").reset_index(drop=True)

    # Filter 1950+ for enough data
    df_long = df_long[df_long["Year"] >= 1950].reset_index(drop=True)
    return df_long, raw


def _build_gistemp_oric(df: pd.DataFrame) -> pd.DataFrame:
    """Build ORI-C columns from GISTEMP series."""
    n = len(df)
    T = df["anomaly"].to_numpy(dtype=float)

    # ── O: ecosystem capacity = inverse of positive temperature anomaly ───────
    T_pos = np.clip(T, 0, None)
    O = 1.0 - robust_minmax(T_pos)

    # ── R: climate resilience = inverse of 10-year rolling std ───────────────
    window = 120  # months = 10 years
    roll_std = pd.Series(T).rolling(window, min_periods=12).std().fillna(0).to_numpy()
    R = 1.0 - robust_minmax(roll_std)

    # ── I: system integration = land-ocean coherence proxy ───────────────────
    # Approximation: rolling autocorrelation at lag 12 (annual cycle coherence)
    lag12 = np.concatenate([T[:12], T[:-12]])
    coherence = np.zeros(n)
    win = 60
    for i in range(win, n):
        x = T[i-win:i]
        y = lag12[i-win:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coherence[i] = float(np.corrcoef(x, y)[0, 1])
    I = robust_minmax(np.clip(coherence, 0, None))

    # ── S: symbolic stock = cumulative fraction below +1°C threshold ─────────
    threshold_C = 1.0
    below = (T < threshold_C).astype(float)
    S = np.cumsum(below) / (np.arange(n) + 1.0)
    S = minmax(S)

    # ── demand: normalised positive anomaly ───────────────────────────────────
    demand = robust_minmax(T_pos)

    return pd.DataFrame({
        "t":        np.arange(n),
        "O":        np.clip(O, 0, 1),
        "R":        np.clip(R, 0, 1),
        "I":        np.clip(I, 0, 1),
        "S":        np.clip(S, 0, 1),
        "demand":   np.clip(demand, 0, 1),
        "date":     df["date"].dt.strftime("%Y-%m"),
        "T_anomaly_C": T,
    })


# ── proxy_spec.json ───────────────────────────────────────────────────────────

def _proxy_spec(dataset_id: str, sector: str = "climate") -> dict:
    return {
        "dataset_id":   dataset_id,
        "spec_version": "2.1",
        "sector":       sector,
        "time_column":  "t",
        "time_mode":    "index",
        "columns": [
            {
                "source_column": "O",
                "oric_role": "O",
                "oric_variable": "O",
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": "Inverse of physical stress indicator.",
                "manipulability_note": "Derived from observed physical data; not subject to reporting bias."
            },
            {
                "source_column": "R",
                "oric_role": "R",
                "oric_variable": "R",
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": "Inverse rolling volatility — resilience proxy.",
                "manipulability_note": "Computed from rolling window; insensitive to single-point shocks."
            },
            {
                "source_column": "I",
                "oric_role": "I",
                "oric_variable": "I",
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": "Coupling / coherence index across sub-systems.",
                "manipulability_note": "Requires correlated perturbation across multiple sub-systems to affect."
            },
            {
                "source_column": "demand",
                "oric_role": "demand",
                "oric_variable": "demand",
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": "External environmental pressure indicator.",
                "manipulability_note": "Directly observed physical variable; not manipulable."
            },
            {
                "source_column": "S",
                "oric_role": "S",
                "oric_variable": "S",
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": "Cumulative symbolic safety stock (historical fraction in safe zone).",
                "manipulability_note": "Cumulative construct; resistant to short-term manipulation."
            },
        ],
    }


# ── Main CLI ──────────────────────────────────────────────────────────────────

def run(pilot_id: str, outdir: Path, repo_root: Path) -> None:
    outdir = outdir.resolve()
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "co2_mauna_loa":
        df_raw, raw_bytes = _fetch_co2(outdir, raw_dir)
        df_oric = _build_co2_oric(df_raw)
        spec = _proxy_spec("sector_climate.pilot_co2_mauna_loa.real.v1")
    elif pilot_id == "gistemp":
        df_raw, raw_bytes = _fetch_gistemp(outdir, raw_dir)
        df_oric = _build_gistemp_oric(df_raw)
        spec = _proxy_spec("sector_climate.pilot_gistemp.real.v1")
    else:
        print(f"Unknown pilot_id: {pilot_id}", file=sys.stderr)
        sys.exit(1)

    # Save outputs
    save_real_csv(df_oric, outdir / "real.csv")
    (outdir / "proxy_spec.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False)
    )
    write_manifest(
        outdir / "fetch_manifest.json",
        pilot_id=pilot_id,
        sector="climate",
        n_rows=len(df_oric),
        sha256=sha256_bytes(raw_bytes) if isinstance(raw_bytes, bytes) else "n/a",
    )
    print(f"[climate/{pilot_id}] Saved {len(df_oric)} rows to {outdir/'real.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch climate real data")
    parser.add_argument("--pilot-id", required=True,
                        choices=["co2_mauna_loa", "gistemp"],
                        help="Pilot to fetch")
    parser.add_argument("--outdir", required=True, type=Path,
                        help="Output directory")
    args = parser.parse_args()
    run(args.pilot_id, args.outdir, REPO_ROOT)


if __name__ == "__main__":
    main()
