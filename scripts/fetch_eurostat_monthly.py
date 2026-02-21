"""
fetch_eurostat_monthly.py — Download Eurostat monthly indicators and build an ORI-C-ready CSV.

Sources (Eurostat REST API, public):
  O  = sts_inpr_m / STS_INPR_M : Industrial Production Index, monthly
  R  = ei_bsin_q / EI_BSIN_Q   : Capacity utilisation (quarterly → interpolated monthly)
  I  = prc_hicp_midx            : HICP index (≈ CPI) used as integration/price-level proxy
  demand = nrg_cb_m             : Total energy consumption, monthly (demand pressure)
  S  = env_ac_aigg_q            : GHG emissions quarterly → interpolated (symbolic stock proxy)

Country/aggregate: EU27 default (geo=EU27_2020), or pass --geo FR, DE, EE, etc.

Output: 03_Data/real/eurostat_monthly/real.csv
  Columns: t, O, R, I, demand  (normalized to [0,1])

Usage:
  pip install pandas requests
  python scripts/fetch_eurostat_monthly.py --geo EU27_2020 --outdir 03_Data/real/eurostat_monthly

Note: Eurostat monthly series typically start from 2000 → ~280 rows.
For T2 threshold detection (needs ~300 steps) you may want 2000-present
or combine with FRED data (see fetch_fred_monthly.py).
"""
from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

import pandas as pd
import requests

ESTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def fetch_estat(dataset: str, params: dict, session: requests.Session) -> pd.Series:
    """Fetch a Eurostat time series and return a monthly pd.Series indexed by date."""
    url = f"{ESTAT_BASE}/{dataset}"
    params = {"format": "JSON", "lang": "EN", **params}
    print(f"  GET {dataset} …", end=" ", flush=True)
    r = session.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()

    # Parse Eurostat JSON-stat format
    dims = data["dimension"]
    time_dim = dims["time"]
    time_vals = list(time_dim["category"]["index"].keys())   # e.g. "2000M01"
    value_list = data["value"]

    # Build series (values are in flattened row-major order; find time offset)
    dim_sizes = [len(dims[d]["category"]["index"]) for d in data["id"]]
    time_idx = data["id"].index("time")
    n_time = dim_sizes[time_idx]

    # For single-filter calls there's usually one value per time point
    values = [value_list.get(str(i)) for i in range(len(time_vals))]
    dates = pd.to_datetime([t.replace("M", "-") for t in time_vals], format="%Y-%m")
    s = pd.Series(values, index=dates, dtype=float)
    s.index.name = "date"
    s = s.sort_index()
    print(f"{s.notna().sum()} rows ({s.index[0].date()} – {s.index[-1].date()})")
    return s


def normalize_minmax(s: pd.Series) -> pd.Series:
    mn, mx = s.min(), s.max()
    if mx == mn:
        return s * 0.0
    return ((s - mn) / (mx - mn)).clip(0.0, 1.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--geo", default="EU27_2020", help="Eurostat geo code (default: EU27_2020)")
    ap.add_argument("--outdir", default="03_Data/real/eurostat_monthly")
    ap.add_argument("--start", default="2000-01-01")
    args = ap.parse_args()

    geo = args.geo
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "ORI-C-data-fetch/1.0"

    print(f"Downloading Eurostat monthly series (geo={geo}):")

    series: dict[str, pd.Series] = {}

    # O: Industrial production index (nace_r2=C = manufacturing)
    try:
        series["O"] = fetch_estat("sts_inpr_m", {
            "geo": geo, "indic": "PRD", "s_adj": "CA",
            "nace_r2": "C", "unit": "I15"
        }, session)
    except Exception as e:
        print(f"  ERROR O: {e}", file=sys.stderr)
        sys.exit(1)

    # R: Capacity utilisation (quarterly → resample to monthly)
    try:
        # Dataset ei_bsin_q uses indic_ei
        r_q = fetch_estat("ei_bsin_q", {
            "geo": geo, "indic_ei": "BS-CAPU", "s_adj": "SA"
        }, session)
        # Quarterly index to monthly dates, then interpolate
        series["R"] = r_q.resample("MS").interpolate("linear")
    except Exception as e:
        print(f"  WARN R (capacity utilisation): {e} — will use HICP as fallback R",
              file=sys.stderr)
        series["R"] = None

    # I: HICP overall index (price-level integration proxy)
    try:
        series["I"] = fetch_estat("prc_hicp_midx", {
            "geo": geo, "coicop": "CP00", "unit": "I15"
        }, session)
    except Exception as e:
        print(f"  ERROR I: {e}", file=sys.stderr)
        sys.exit(1)

    # demand: producer prices (industrial output prices) as external pressure
    try:
        series["demand"] = fetch_estat("sts_inppd_m", {
            "geo": geo, "indic": "PRD", "s_adj": "NSA",
            "nace_r2": "MIG_CAG", "unit": "I15"
        }, session)
    except Exception as e:
        print(f"  WARN demand (PPI): {e} — using HICP energy as fallback", file=sys.stderr)
        try:
            series["demand"] = fetch_estat("prc_hicp_midx", {
                "geo": geo, "coicop": "CP045", "unit": "I15"  # energy HICP
            }, session)
        except Exception as e2:
            print(f"  ERROR demand: {e2}", file=sys.stderr)
            sys.exit(1)

    # If R failed, use negative of HICP (tighter prices = reduced resilience)
    if series.get("R") is None:
        series["R"] = 1.0 - normalize_minmax(series["I"])

    # Align
    df = pd.DataFrame({k: v for k, v in series.items() if v is not None})
    df = df.resample("MS").first()
    df = df.loc[args.start:]
    df = df.ffill().bfill()

    print(f"\nDate range: {df.index[0].date()} – {df.index[-1].date()} ({len(df)} rows)")
    if len(df) < 120:
        print("WARNING: fewer than 120 rows — T2 threshold detection may not fire. "
              "Consider extending start date or using FRED (fetch_fred_monthly.py).",
              file=sys.stderr)

    for col in df.columns:
        df[col] = normalize_minmax(df[col])

    df.index.name = "date"
    df = df.reset_index()
    df.insert(0, "t", range(len(df)))

    out_path = outdir / "real.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved → {out_path}  ({len(df)} rows)")

    cap = df["O"] * df["R"] * df["I"]
    sigma = (df["demand"] - cap).clip(lower=0)
    print(f"Sigma > 0: {(sigma > 0).sum()} / {len(df)} rows  (max {sigma.max():.4f})")

    print("\nNext step:")
    print(f"  PYTHONPATH=04_Code python 04_Code/pipeline/run_real_data_canonical_suite.py \\")
    print(f"    --input {out_path} \\")
    print(f"    --outdir 05_Results/real/eurostat_monthly \\")
    print(f"    --col-time date --col-O O --col-R R --col-I I \\")
    print(f"    --col-demand demand --normalize none \\")
    print(f"    --baseline-n 60 --pre-horizon 100 --post-horizon 100 --lags 1-6 \\")
    print(f"    --alpha 0.01 --k 2.5 --m 3")


if __name__ == "__main__":
    main()
