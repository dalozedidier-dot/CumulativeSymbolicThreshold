"""
fetch_fred_monthly.py — Download FRED monthly macro series and build an ORI-C-ready CSV.

Sources (all public, no API key needed):
  O  = INDPRO  : Industrial Production Index           (monthly, since 1919)
  R  = TCU     : Capacity Utilization, Total Industry  (monthly, since 1967)
  I  = T10YFF  : 10Y Treasury minus Fed Funds (yield curve spread — integration/credit proxy)
  demand = CPIAUCSL : CPI All Items (demand pressure proxy)
  S  = DCOILWTICO : WTI oil price (symbolic commodity stock proxy)  [optional]

Output: 03_Data/real/fred_monthly/real.csv
  Columns: t, O, R, I, demand, S  (all normalized to [0,1] via min-max)
  Rows: 1967-01 onward (TCU limits the start), ~700 rows

Usage:
  pip install pandas requests
  python scripts/fetch_fred_monthly.py --outdir 03_Data/real/fred_monthly

Note on ORI-C suitability:
  - 700+ monthly rows → T2 threshold detection feasible (needs ~300 steps)
  - Demand (CPI) regularly exceeds normalized Cap during oil shocks (1973, 1979, 2008, 2022)
  - Expected results: T1 ACCEPT, T2 ACCEPT (crisis threshold), T4/T7 ACCEPT (monetary ↔ symbolic)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests


FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="

SERIES = {
    "O": "INDPRO",       # Industrial Production Index (normalized, 2017=100)
    "R": "TCU",          # Capacity Utilization % (0–100)
    "I": "T10YFF",       # 10Y-FF spread (integration / credit conditions proxy)
    "demand": "CPIAUCSL",# CPI All Items, index (demand pressure)
    "S": "DCOILWTICO",   # WTI crude oil (symbolic commodity stock)
}


def fetch_series(series_id: str, session: requests.Session) -> pd.Series:
    url = FRED_BASE + series_id
    print(f"  Fetching {series_id} …", end=" ", flush=True)
    r = session.get(url, timeout=30)
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(r.text), parse_dates=["DATE"], index_col="DATE")
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    s.name = series_id
    print(f"{s.notna().sum()} non-null rows ({s.index[0].date()} – {s.index[-1].date()})")
    return s


def normalize_minmax(s: pd.Series) -> pd.Series:
    mn, mx = s.min(), s.max()
    if mx == mn:
        return s * 0.0
    return ((s - mn) / (mx - mn)).clip(0.0, 1.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default="03_Data/real/fred_monthly",
                    help="Output directory (default: 03_Data/real/fred_monthly)")
    ap.add_argument("--start", default="1967-01-01",
                    help="Start date (default: 1967-01-01, limited by TCU availability)")
    ap.add_argument("--end", default=None,
                    help="End date (default: latest available)")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "ORI-C-data-fetch/1.0"

    print("Downloading FRED series:")
    raw: dict[str, pd.Series] = {}
    for col, sid in SERIES.items():
        try:
            raw[col] = fetch_series(sid, session)
        except Exception as exc:
            print(f"  ERROR fetching {sid}: {exc}", file=sys.stderr)
            sys.exit(1)

    # Align on monthly frequency
    df = pd.DataFrame(raw)
    df.index = pd.to_datetime(df.index)
    df = df.resample("MS").first()          # month-start
    df = df.loc[args.start:]
    if args.end:
        df = df.loc[: args.end]

    # I = T10YFF can be negative → shift to [0,1]
    # (negative spread = inverted curve = financial stress)
    # We want HIGH values = good integration, LOW = stress → invert sign first
    df["I"] = -df["I"]   # invert: positive when spread is negative (tighter conditions)

    print(f"\nDate range: {df.index[0].date()} – {df.index[-1].date()} ({len(df)} rows)")
    print("Missing values per column:")
    print(df.isna().sum().to_string())

    # Forward-fill then back-fill short gaps (oil price has some)
    df = df.ffill().bfill()

    # Normalize each column to [0, 1]
    for col in ["O", "R", "I", "demand", "S"]:
        df[col] = normalize_minmax(df[col])

    df.index.name = "date"
    df = df.reset_index()
    df.insert(0, "t", range(len(df)))

    # Save
    out_path = outdir / "real.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved → {out_path}  ({len(df)} rows, columns: {list(df.columns)})")

    # Quick sanity: rows where demand > Cap
    cap = df["O"] * df["R"] * df["I"]
    sigma = (df["demand"] - cap).clip(lower=0)
    print(f"\nSigma > 0 (demand > Cap): {(sigma > 0).sum()} / {len(df)} rows")
    print(f"Sigma max: {sigma.max():.4f}")

    print("\nNext step:")
    print(f"  PYTHONPATH=04_Code python 04_Code/pipeline/run_real_data_canonical_suite.py \\")
    print(f"    --input {out_path} \\")
    print(f"    --outdir 05_Results/real/fred_monthly \\")
    print(f"    --col-time date --time-mode index \\")
    print(f"    --col-O O --col-R R --col-I I \\")
    print(f"    --col-demand demand --col-S S \\")
    print(f"    --normalize none \\")
    print(f"    --baseline-n 60 --pre-horizon 120 --post-horizon 120 --lags 1-6 \\")
    print(f"    --alpha 0.01 --k 2.5 --m 3")


if __name__ == "__main__":
    main()
