"""fetch_real_data.py — Cosmo sector real-data fetcher.

Sources (all public, no authentication required):

  solar — Monthly solar indices from two authoritative public sources:

    1. SIDC International Sunspot Number v2 (monthly totals)
       URL: https://www.sidc.be/SILSO/DATA/SN_m_tot_V2.0.csv
       Format: year  month  decimal_year  SN  SN_error  n_obs  provisional
       License: CC BY-NC 4.0 — Royal Observatory of Belgium

    2. GFZ Potsdam Kp/Ap/SN/F10.7 combined daily file
       URL: https://kp.gfz-potsdam.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt
       Contains: year month day  Kp×8  ap×8  Ap  SN  F107obs  F107adj
       → Aggregated to monthly means here.
       License: CC BY 4.0 — GFZ Helmholtz Centre Potsdam

    Period: 1960-01 → present (monthly, ~780 rows ≈ 65 years = ~6 solar cycles)

ORI-C mapping (solar):
  O = smoothed_ssn_norm          → emission regularity (organisation)
  R = 1 − kp_monthly_mean_norm   → magnetic resilience (lower Kp = more stable)
  I = f107_adj_norm              → multi-wavelength coherence (integration)
  S = cumulative_flare_proxy     → persistent structured solar signal (symbolic stock)
                                    computed as cumsum_norm of (ssn above cycle median)
  demand = ap_monthly_mean_norm  → geomagnetic demand on magnetosphere

  instrument_gap column:
    1 at known GOES/sensor transitions that represent symbolic cuts (U(t)):
    - 1965-01: Transition from visual to automated SSN counting
    - 1994-01: GOES-7 → GOES-8 transition
    - 2016-11: GOES-13 → GOES-16 transition
    - 2017-01: SSN v1 → v2 revision (SIDC recalibration)
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
    download_bytes, robust_minmax, cumsum_norm,
    save_real_csv, write_manifest, sha256_bytes,
)

REPO_ROOT = _HERE.parent.parent.parent

# ── URLs ──────────────────────────────────────────────────────────────────────

_SIDC_SN_URL = "https://www.sidc.be/SILSO/DATA/SN_m_tot_V2.0.csv"
_GFZ_URL     = "https://kp.gfz-potsdam.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"


# ── Known instrument/calibration transitions (symbolic cut annotation) ────────

_INSTRUMENT_GAPS = [
    ("1965-01", "SSN counting methodology change — automated baseline"),
    ("1994-01", "GOES-7 → GOES-8 sensor transition"),
    ("2016-11", "GOES-13 → GOES-16 transition (X-ray flux recalibration)"),
    ("2017-01", "SIDC SSN v1 → v2 recalibration — systematic offset corrected"),
]


# ── GFZ parser ────────────────────────────────────────────────────────────────

def _parse_gfz(data: bytes) -> pd.DataFrame:
    """
    Parse GFZ Kp/ap/Ap/SN/F107 daily file → monthly means.

    File format (after header lines starting with #):
      YYYY MM DD  Kp1..Kp8  ap1..ap8  Ap  SN  F107obs  F107adj  D
    We need: Ap (daily geomagnetic index), SN (sunspot), F107adj.
    """
    lines = data.decode("utf-8", errors="replace").splitlines()
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        # Expect at least 30 fields: year, month, day, 8×Kp, 8×ap, Ap, SN, F107obs, F107adj
        if len(parts) < 30:
            continue
        try:
            year  = int(parts[0])
            month = int(parts[1])
            # parts[3:11] = Kp×8 (tenths), parts[11:19] = ap×8, parts[19] = Ap
            # parts[20] = SN, parts[21] = F107obs, parts[22] = F107adj
            # Newer format has a status flag as last column
            ap_daily = float(parts[19])
            sn_daily = float(parts[20])
            # F107adj is at index 22 in the standard format
            f107     = float(parts[22]) if len(parts) > 22 else float(parts[21])
            if ap_daily < 0 or sn_daily < 0 or f107 < 0:
                continue
            rows.append({"year": year, "month": month,
                         "ap": ap_daily, "sn": sn_daily, "f107adj": f107})
        except (ValueError, IndexError):
            continue

    if not rows:
        raise ValueError("GFZ file parsed 0 valid rows — format may have changed")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01"
    )
    # Monthly mean
    monthly = (
        df.groupby("date", sort=True)
          .agg(ap_mean=("ap", "mean"), sn_mean=("sn", "mean"), f107adj_mean=("f107adj", "mean"))
          .reset_index()
    )
    return monthly


# ── SIDC parser ───────────────────────────────────────────────────────────────

def _parse_sidc(data: bytes) -> pd.DataFrame:
    """
    Parse SIDC SN_m_tot_V2.0.csv.
    Format: year;month;decimal_year;SN;SN_error;n_obs;provisional
    (semicolon-separated)
    """
    lines = data.decode("utf-8", errors="replace").splitlines()
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Try semicolon first, then whitespace
        if ";" in stripped:
            parts = stripped.split(";")
        else:
            parts = stripped.split()
        if len(parts) < 4:
            continue
        try:
            year  = int(parts[0])
            month = int(parts[1])
            sn    = float(parts[3])
            if sn < 0:
                sn = np.nan
            rows.append({"year": year, "month": month, "ssn": sn})
        except (ValueError, IndexError):
            continue

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01"
    )
    return df[["date", "ssn"]].set_index("date").sort_index()


# ── Main fetch ────────────────────────────────────────────────────────────────

def fetch_solar(outdir: Path, start_year: int = 1960) -> pd.DataFrame:
    """
    Fetch and process solar indices → monthly ORI-C DataFrame.
    """
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("\n[cosmo/solar] Fetching SIDC sunspot number...")
    print("  Source: SIDC — CC BY-NC 4.0 — Royal Observatory of Belgium")
    sidc_data = download_bytes(_SIDC_SN_URL)
    sidc_sha  = sha256_bytes(sidc_data)
    (raw_dir / "sidc_sn_monthly.csv").write_bytes(sidc_data)

    print("\n[cosmo/solar] Fetching GFZ Kp/ap/SN/F10.7 combined file...")
    print("  Source: GFZ Potsdam — CC BY 4.0 — Helmholtz Centre Potsdam")
    gfz_data = download_bytes(_GFZ_URL, timeout=180)
    gfz_sha  = sha256_bytes(gfz_data)
    (raw_dir / "gfz_kp_ap_sn_f107.txt").write_bytes(gfz_data)

    # Parse
    df_sidc = _parse_sidc(sidc_data)
    df_gfz  = _parse_gfz(gfz_data).set_index("date").sort_index()

    # Merge on date index
    df = df_sidc.join(df_gfz, how="outer").sort_index()

    # Prefer GFZ SN where both available (more complete); fallback to SIDC
    if "sn_mean" in df.columns:
        df["ssn_combined"] = df["sn_mean"].fillna(df["ssn"])
    else:
        df["ssn_combined"] = df["ssn"]

    # Filter to start_year → present
    df = df[df.index >= f"{start_year}-01-01"]
    df = df.dropna(subset=["ssn_combined"])

    # Forward-fill gaps (≤ 3 months) in F10.7 and ap
    for col in ["f107adj_mean", "ap_mean"]:
        if col in df.columns:
            df[col] = df[col].interpolate(method="linear", limit=3)

    n = len(df)
    print(f"  Merged: {n} monthly rows "
          f"({df.index[0].strftime('%Y-%m')} → {df.index[-1].strftime('%Y-%m')})")

    ssn  = pd.Series(df["ssn_combined"].values, dtype=float)
    ap   = pd.Series(df["ap_mean"].values if "ap_mean" in df.columns
                     else np.zeros(n), dtype=float)
    f107 = pd.Series(df["f107adj_mean"].values if "f107adj_mean" in df.columns
                     else ssn * 0.8 + 68, dtype=float)   # rough proxy if missing

    # ── ORI-C mapping ──────────────────────────────────────────────────────

    # O: smoothed SSN (12-month running mean) → emission regularity / organisation
    ssn_smooth = ssn.rolling(12, min_periods=6).mean().fillna(method="bfill")
    O = robust_minmax(ssn_smooth)

    # R: 1 − Kp_monthly_mean_norm → magnetic resilience
    R = 1.0 - robust_minmax(ap.fillna(ap.median()))

    # I: F10.7 adjusted norm → multi-wavelength coherence
    I = robust_minmax(f107.fillna(f107.median()))

    # S: cumulative structured solar signal
    # = cumsum_norm of SSN above the long-term median (persistent active-phase memory)
    cycle_median = float(ssn.median())
    ssn_above    = (ssn - cycle_median).clip(lower=0)
    S = cumsum_norm(robust_minmax(ssn_above), decay=0.004)

    # demand: ap index (geomagnetic activity)
    demand = robust_minmax(ap.fillna(ap.median()))

    # ── Instrument gap annotation ──────────────────────────────────────────
    dates = df.index.strftime("%Y-%m")
    instrument_gap = pd.Series(0, index=range(n))
    for gap_date, _ in _INSTRUMENT_GAPS:
        mask = (dates == gap_date)
        if mask.any():
            idx = np.where(mask)[0][0]
            instrument_gap.iloc[max(0, idx-1): idx+2] = 1

    out = pd.DataFrame({
        "t":              range(n),
        "date":           dates,
        "O":              O.values,
        "R":              R.values,
        "I":              I.values,
        "S":              S.values,
        "demand":         demand.values,
        "instrument_gap": instrument_gap.values,   # U(t) symbolic cut marker
        "ssn_raw":        ssn.values,
        "ssn_smooth_raw": ssn_smooth.values,
        "f107_raw":       f107.values,
        "ap_raw":         ap.values,
    })

    write_manifest(
        outdir / "fetch_manifest.json",
        sector="cosmo",
        pilot="solar",
        sources=[
            {"url": _SIDC_SN_URL, "sha256": sidc_sha,
             "license": "CC BY-NC 4.0", "provider": "SIDC / Royal Observatory of Belgium"},
            {"url": _GFZ_URL, "sha256": gfz_sha,
             "license": "CC BY 4.0", "provider": "GFZ Helmholtz Centre Potsdam"},
        ],
        n_rows=n,
        date_range=(df.index[0].strftime("%Y-%m"), df.index[-1].strftime("%Y-%m")),
        notes=(
            f"Monthly solar indices from {start_year}. SSN v2. F10.7 adjusted. "
            f"Instrument gaps annotated at: {[d for d,_ in _INSTRUMENT_GAPS]}. "
            "instrument_gap=1 is the Cosmo symbolic cut (U(t))."
        ),
    )

    return out


# ── Proxy spec ────────────────────────────────────────────────────────────────

def _write_proxy_spec(outdir: Path) -> None:
    spec = {
        "dataset_id":   "cosmo_solar_real",
        "sector":       "cosmo",
        "pilot":        "solar",
        "spec_version": "1.1",
        "data_type":    "real",
        "time_column":  "date",
        "time_mode":    "value",
        "normalization": "already_normalized",
        "data_source":  "SIDC (CC BY-NC 4.0) + GFZ Potsdam (CC BY 4.0)",
        "data_url":     _SIDC_SN_URL,
        "perturbation_column": "instrument_gap",
        "perturbation_type":   "symbolic_cut",
        "perturbation_note":   (
            "instrument_gap=1 marks known sensor/calibration transitions "
            "(GOES generations, SIDC v1→v2). Standard Cosmo T6 test."
        ),
        "columns": [
            {"oric_role": "O", "source_column": "O", "direction": "positive",
             "fragility_score": 0.22,
             "fragility_note": "SSN v2 recalibrated in 2015; pre-1900 data less reliable",
             "manipulability_note": "Not manipulable — physical observation",
             "description": "Smoothed SSN norm (12-month rolling mean): solar emission regularity"},
            {"oric_role": "R", "source_column": "R", "direction": "positive",
             "fragility_score": 0.25,
             "fragility_note": "ap is global average; local effects differ significantly",
             "manipulability_note": "Not manipulable",
             "description": "1 − ap_norm: magnetic resilience (lower activity = more stable)"},
            {"oric_role": "I", "source_column": "I", "direction": "positive",
             "fragility_score": 0.20,
             "fragility_note": "F10.7 adjusted values used; consistent since 1947",
             "manipulability_note": "Not manipulable",
             "description": "F10.7 adjusted flux norm: multi-wavelength emission coherence"},
            {"oric_role": "S", "source_column": "S", "direction": "positive",
             "fragility_score": 0.28,
             "fragility_note": "Cumsum threshold = long-term SSN median (pre-registered)",
             "manipulability_note": "Not manipulable; threshold is pre-registered",
             "description": "Cumulative SSN above cycle median (persistent solar memory)"},
            {"oric_role": "demand", "source_column": "demand", "direction": "positive",
             "fragility_score": 0.22,
             "fragility_note": "ap is a global average; storm-level events dominate monthly mean",
             "manipulability_note": "Not manipulable",
             "description": "ap geomagnetic index norm: environmental demand on magnetosphere"},
        ],
    }
    spec_path = outdir / "proxy_spec.json"
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"  [proxy_spec] → {spec_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real cosmo sector data")
    parser.add_argument("--pilot",      choices=["solar", "all"], default="all")
    parser.add_argument("--start-year", type=int, default=1960)
    parser.add_argument("--outdir",     default=None)
    args = parser.parse_args()

    base = Path(args.outdir) if args.outdir else (REPO_ROOT / "03_Data/sector_cosmo/real")
    pilots = ["solar"] if args.pilot == "all" else [args.pilot]

    for pilot in pilots:
        out = base / f"pilot_{pilot}"
        out.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*60}\n  COSMO / {pilot.upper()}\n{'='*60}")
        try:
            df = fetch_solar(out, start_year=args.start_year)
            save_real_csv(df, out / "real.csv")
            _write_proxy_spec(out)
            print(f"\n  ✓ {pilot}: {len(df)} rows → {out}/real.csv")
        except Exception as exc:
            print(f"\n  ✗ {pilot}: FAILED — {exc}")
            raise

    print("\nCosmo fetch complete.")


if __name__ == "__main__":
    main()
