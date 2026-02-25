"""fetch_real_data.py — Infra sector real-data fetcher.

Sources (all public, no authentication required):

  finance — FRED direct CSV download (no API key needed)
    Each series accessed via:
      https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>
    This is the same URL used by the "Download data" button on fred.stlouisfed.org.
    No registration or API key required.

    Series fetched:
      VIXCLS   — CBOE Volatility Index (daily → monthly mean)
      BAMLC0A0CM — ICE BofA US Corp Index OAS (IG credit spread, daily → monthly)
      FEDFUNDS — Federal Funds Effective Rate (monthly, already monthly)
      SP500    — S&P 500 Index (daily → monthly last)
      GS10     — 10-Year Treasury Constant Maturity Rate (monthly)

    Period: 2004-01-01 → present (monthly, ~250 rows ≈ 21 years)
    License: FRED data is public domain / open use for research

ORI-C mapping (finance):
  O = 1 / (1 + VIX/100) norm          → inverse implied volatility (organisation)
  R = 1 − ig_spread_norm              → inverse credit stress (resilience / liquidity)
  I = |rolling_corr(SP500, GS10)|     → equity-bond coupling (integration)
  S = cumsum_norm(fedfunds_change_neg) → accumulated policy accommodation memory
                                         (rate cuts = positive impulse → symbolic stock)
  demand = ig_spread_norm             → credit spread (environmental stress demand)
  U = 1 at FOMC/ECB decision dates where rate change ≥ 25 bps
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
    rolling_corr, save_real_csv, write_manifest, sha256_bytes,
)

REPO_ROOT = _HERE.parent.parent.parent

# ── FRED direct-download URLs (no API key required) ───────────────────────────

_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="

_FRED_SERIES = {
    "VIXCLS":      "CBOE Volatility Index (daily)",
    "BAMLC0A0CM":  "ICE BofA US Corp Index OAS — investment-grade credit spread (daily)",
    "FEDFUNDS":    "Federal Funds Effective Rate (monthly)",
    "SP500":       "S&P 500 Index (daily)",
    "GS10":        "10-Year Treasury Constant Maturity Rate (monthly)",
}

# ── Known FOMC events: large rate decisions ≥ 25 bps → U(t) annotation ────────

_FOMC_EVENTS_MONTHLY = [
    "2001-01", "2001-03", "2001-04", "2001-05", "2001-06", "2001-08",
    "2001-09", "2001-10", "2001-11", "2007-09", "2007-10", "2007-12",
    "2008-01", "2008-03", "2008-04", "2008-10",
    "2015-12",
    "2022-03", "2022-05", "2022-06", "2022-07", "2022-09", "2022-11", "2022-12",
    "2023-02", "2023-03", "2023-05", "2023-07",
]


# ── Fetch one FRED series ─────────────────────────────────────────────────────

def _fetch_fred_series(series_id: str, raw_dir: Path) -> pd.Series:
    url  = _FRED_BASE + series_id
    data = download_bytes(url)
    sha  = sha256_bytes(data)
    (raw_dir / f"fred_{series_id}.csv").write_bytes(data)

    df = pd.read_csv(io.BytesIO(data), parse_dates=["DATE"])
    df = df.rename(columns={"DATE": "date", series_id: "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna().set_index("date").sort_index()["value"]
    print(f"  {series_id}: {len(df)} rows  sha256={sha[:16]}…")
    return df


# ── Main finance fetch ────────────────────────────────────────────────────────

def fetch_finance(outdir: Path, start: str = "2004-01-01") -> pd.DataFrame:
    """
    Fetch FRED series, aggregate to monthly, compute ORI-C columns.
    """
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("\n[infra/finance] Fetching FRED series (direct CSV, no API key)...")
    print("  Source: FRED / St. Louis Fed — public domain")

    shas: dict[str, str] = {}
    raw: dict[str, pd.Series] = {}

    for sid in _FRED_SERIES:
        try:
            raw[sid] = _fetch_fred_series(sid, raw_dir)
        except Exception as exc:
            print(f"  [warn] {sid} failed: {exc}")

    # Mandatory check
    required = {"VIXCLS", "BAMLC0A0CM", "FEDFUNDS", "SP500", "GS10"}
    missing = required - set(raw)
    if missing:
        raise RuntimeError(
            f"Could not download required FRED series: {missing}. "
            "Check network connectivity."
        )

    # ── Resample to monthly ────────────────────────────────────────────────
    idx = pd.date_range(start=start, end=pd.Timestamp.now(), freq="MS")

    def monthly_mean(s: pd.Series) -> pd.Series:
        return s.resample("MS").mean().reindex(idx)

    def monthly_last(s: pd.Series) -> pd.Series:
        return s.resample("MS").last().reindex(idx)

    vix    = monthly_mean(raw["VIXCLS"])
    spread = monthly_mean(raw["BAMLC0A0CM"])
    fed    = monthly_mean(raw["FEDFUNDS"])      # already monthly
    sp500  = monthly_last(raw["SP500"])
    gs10   = monthly_last(raw["GS10"])

    # Compute log returns for rolling correlation
    sp500_ret = np.log(sp500 / sp500.shift(1))
    gs10_ret  = gs10.diff()   # level change for bonds

    # Forward-fill gaps ≤ 3 months
    for s in [vix, spread, fed, sp500, gs10, sp500_ret, gs10_ret]:
        s.interpolate(method="linear", limit=3, inplace=True)

    # Drop rows where VIX or spread is NaN
    valid = vix.notna() & spread.notna() & fed.notna()
    vix    = vix[valid]
    spread = spread[valid]
    fed    = fed[valid]
    sp500_ret = sp500_ret[valid]
    gs10_ret  = gs10_ret[valid]

    n    = len(vix)
    idx2 = vix.index

    print(f"  Monthly: {n} rows "
          f"({idx2[0].strftime('%Y-%m')} → {idx2[-1].strftime('%Y-%m')})")

    # ── ORI-C mapping ──────────────────────────────────────────────────────

    # O: inverse implied volatility — 1 / (1 + VIX/100)
    vix_s    = pd.Series(vix.values, dtype=float)
    org_raw  = 1.0 / (1.0 + vix_s / 100.0)
    O = robust_minmax(org_raw)

    # R: 1 − spread_norm (lower spread = more resilient / liquid)
    spread_s = pd.Series(spread.values, dtype=float)
    R = 1.0 - robust_minmax(spread_s)

    # I: equity-bond rolling correlation (24-month window)
    sp_ret_s  = pd.Series(sp500_ret.values, dtype=float).fillna(0)
    gs10_ret_s = pd.Series(gs10_ret.values, dtype=float).fillna(0)
    I_raw = rolling_corr(sp_ret_s, gs10_ret_s, window=24)
    I = I_raw.fillna(method="bfill").fillna(0.5)

    # S: accumulated policy accommodation (rate-cut memory)
    # Fed rate cuts (negative changes) = positive impulse to symbolic stock
    fed_s      = pd.Series(fed.values, dtype=float)
    fed_change = fed_s.diff().fillna(0)
    rate_cut   = (-fed_change).clip(lower=0)   # only cuts, not hikes
    S = cumsum_norm(robust_minmax(rate_cut), decay=0.006)

    # demand: IG credit spread (stress demand on financial system)
    demand = robust_minmax(spread_s)

    # U(t): FOMC large-decision events
    dates_str = idx2.strftime("%Y-%m")
    U = pd.Series([1 if d in _FOMC_EVENTS_MONTHLY else 0 for d in dates_str],
                  dtype=float)

    out = pd.DataFrame({
        "t":           range(n),
        "date":        dates_str,
        "O":           O.values,
        "R":           R.values,
        "I":           I.values,
        "S":           S.values,
        "demand":      demand.values,
        "U":           U.values,
        "vix_raw":     vix_s.values,
        "ig_spread_raw": spread_s.values,
        "fedfunds_raw":  fed_s.values,
        "sp500_logret":  sp_ret_s.values,
        "gs10_chg":      gs10_ret_s.values,
    })

    write_manifest(
        outdir / "fetch_manifest.json",
        sector="infra",
        pilot="finance",
        sources=[
            {"url": _FRED_BASE + sid, "series": sid,
             "description": desc, "license": "public domain / FRED open use"}
            for sid, desc in _FRED_SERIES.items()
        ],
        n_rows=n,
        date_range=(idx2[0].strftime("%Y-%m"), idx2[-1].strftime("%Y-%m")),
        notes=(
            "Monthly aggregation: VIX/spread = mean, SP500 = last, GS10 = last. "
            "U=1 at known FOMC large-decision months (rate change ≥ 25 bps). "
            "S = accumulated rate-cut memory (fed funds decrease impulse)."
        ),
    )

    return out


# ── Proxy spec ────────────────────────────────────────────────────────────────

def _write_proxy_spec(outdir: Path) -> None:
    spec = {
        "dataset_id":   "infra_finance_real",
        "sector":       "infra",
        "pilot":        "finance",
        "spec_version": "1.1",
        "data_type":    "real",
        "time_column":  "date",
        "time_mode":    "value",
        "normalization": "already_normalized",
        "data_source":  "FRED — St. Louis Federal Reserve (public domain)",
        "data_url":     "https://fred.stlouisfed.org/",
        "perturbation_column": "U",
        "perturbation_type":   "exogenous_intervention",
        "perturbation_note":   "U=1 marks FOMC large-decision months (rate change ≥ 25 bps).",
        "columns": [
            {"oric_role": "O", "source_column": "O", "direction": "positive",
             "fragility_score": 0.40,
             "fragility_note": "VIX implied vol reflects options pricing, not realised vol",
             "manipulability_note": "Dealers can influence VIX via options positioning",
             "description": "1/(1+VIX/100) norm: inverse implied volatility (financial organisation)"},
            {"oric_role": "R", "source_column": "R", "direction": "positive",
             "fragility_score": 0.42,
             "fragility_note": "IG spread depends on issuer universe composition changes",
             "manipulability_note": "Central bank purchase programmes directly compress spreads",
             "description": "1 − ig_spread_norm: inverse credit stress (resilience / liquidity)"},
            {"oric_role": "I", "source_column": "I", "direction": "positive",
             "fragility_score": 0.55,
             "fragility_note": "Equity-bond correlation is regime-switching by construction; window=24M",
             "manipulability_note": "ETF rebalancing and risk-parity funds affect correlation structurally",
             "description": "Equity-bond rolling |Pearson r| (24M): financial integration"},
            {"oric_role": "S", "source_column": "S", "direction": "positive",
             "fragility_score": 0.62,
             "fragility_note": "Rate-cut memory is a simplification of policy credibility",
             "manipulability_note": "Central bank forward guidance directly drives this proxy",
             "description": "Cumulative rate-cut impulse (FEDFUNDS decreases): policy accommodation memory"},
            {"oric_role": "demand", "source_column": "demand", "direction": "positive",
             "fragility_score": 0.38,
             "fragility_note": "OAS spread depends on duration and index rebalancing",
             "manipulability_note": "QE/QT programmes compress/expand spreads directly",
             "description": "IG credit spread (OAS) norm: financial stress demand"},
        ],
    }
    spec_path = outdir / "proxy_spec.json"
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"  [proxy_spec] → {spec_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real infra sector data (FRED)")
    parser.add_argument("--pilot",  choices=["finance", "all"], default="all")
    parser.add_argument("--start",  default="2004-01-01",
                        help="Start date (default: 2004-01-01)")
    parser.add_argument("--outdir", default=None)
    args = parser.parse_args()

    base   = Path(args.outdir) if args.outdir else (REPO_ROOT / "03_Data/sector_infra/real")
    pilots = ["finance"] if args.pilot == "all" else [args.pilot]

    for pilot in pilots:
        out = base / f"pilot_{pilot}"
        out.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*60}\n  INFRA / {pilot.upper()}\n{'='*60}")
        try:
            df = fetch_finance(out, start=args.start)
            save_real_csv(df, out / "real.csv")
            _write_proxy_spec(out)
            print(f"\n  ✓ {pilot}: {len(df)} rows → {out}/real.csv")
        except Exception as exc:
            print(f"\n  ✗ {pilot}: FAILED — {exc}")
            raise

    print("\nInfra fetch complete.")


if __name__ == "__main__":
    main()
