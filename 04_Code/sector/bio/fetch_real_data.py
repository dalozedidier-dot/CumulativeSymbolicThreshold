"""fetch_real_data.py — Bio sector real-data fetcher.

Sources (all public, no authentication required):

  epidemic  — OurWorldInData COVID-19 dataset (France, weekly)
    URL: https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv
    Columns used: new_cases_smoothed_per_million, positive_rate, reproduction_rate,
                  people_vaccinated_per_hundred, new_deaths_smoothed_per_million
    Period: 2020-03-01 → 2023-06-30, weekly (ISO-week resampling)

  ecology   — Hudson Bay Company lynx + snowshoe hare pelt records (1900–1920)
    URL: https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2020/2020-05-26/thesis.csv
    OR:  https://datahub.io/core/lynx-hare-populations/datapackage.json
    Classic Elton & Nicholson (1942) dataset, public domain.
    Annual data resampled/interpolated to monthly for ORI-C (200 rows).

Output (per pilot):
  03_Data/sector_bio/real/pilot_<id>/raw/       ← raw downloaded files
  03_Data/sector_bio/real/pilot_<id>/real.csv   ← normalised ORI-C format
  03_Data/sector_bio/real/pilot_<id>/fetch_manifest.json

ORI-C mapping (epidemic):
  O = 1 − (deaths_per_million_norm)    → organisational capacity: inverse fatality burden
  R = 1 − positive_rate_norm           → resilience: fraction tested negative
  I = 1 / (Rt + 0.1) → norm           → integration: how well intervention controls spread
  S = vaccination_coverage (0→1)       → symbolic stock: cumulative immune memory
  demand = new_cases_per_million_norm  → environmental demand

ORI-C mapping (ecology):
  O = prey_norm (hare pelt count)      → food-web organisation
  R = stability_index (inverse rolling CV of hare) → resilience
  I = coupling_index (hare/lynx rolling corr)      → integration
  S = biodiversity_proxy (cumulative hare*lynx product norm) → symbolic stock
  demand = predator_ratio_norm         → environmental pressure
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add shared utilities to path
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "shared"))
from fetch_utils import (
    download_bytes, robust_minmax, minmax, cumsum_norm,
    rolling_corr, save_real_csv, write_manifest, sha256_bytes,
)

REPO_ROOT = _HERE.parent.parent.parent

# ── URLs ──────────────────────────────────────────────────────────────────────

_OWID_URL = (
    "https://raw.githubusercontent.com/owid/covid-19-data/master/"
    "public/data/owid-covid-data.csv"
)
_LYNXHARE_URL = (
    "https://raw.githubusercontent.com/rfordatascience/tidytuesday/"
    "master/data/2020/2020-05-26/thesis.csv"
)
# Fallback lynx-hare: datahub.io (plain CSV, same data)
_LYNXHARE_FALLBACK_URL = (
    "https://pkgstore.datahub.io/core/lynx-hare-populations/"
    "data_csv/data/3b2acfc5c36f9cc39e7e8c9e75ac2fc2/data_csv.csv"
)


# ── Epidemic ──────────────────────────────────────────────────────────────────

def fetch_epidemic(outdir: Path, country: str = "FRA") -> pd.DataFrame:
    """
    Download OurWorldInData COVID-19 data, filter for `country`, resample weekly.
    Returns processed DataFrame with ORI-C columns.
    """
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[bio/epidemic] Downloading OurWorldInData COVID data (country={country})...")
    print("  Source: OurWorldInData — CC BY 4.0 — https://ourworldindata.org/coronavirus")

    # Stream download: large file (~150 MB), read only needed columns
    data = download_bytes(_OWID_URL)
    sha = sha256_bytes(data)

    raw_path = raw_dir / "owid_covid_raw.csv"
    raw_path.write_bytes(data)

    usecols = [
        "iso_code", "date",
        "new_cases_smoothed_per_million",
        "new_deaths_smoothed_per_million",
        "positive_rate",
        "reproduction_rate",
        "people_vaccinated_per_hundred",
    ]
    df_full = pd.read_csv(
        io.BytesIO(data),
        usecols=lambda c: c in usecols,
        dtype={"iso_code": str, "date": str},
        low_memory=False,
    )

    # Filter country
    df = df_full[df_full["iso_code"] == country].copy()
    if len(df) == 0:
        raise ValueError(
            f"Country '{country}' not found in OurWorldInData. "
            f"Available iso_codes (sample): {df_full['iso_code'].unique()[:10]}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # Keep 2020-03 → 2023-06
    df = df.loc["2020-03-01":"2023-06-30"]

    # Resample to weekly (ISO week, Monday)
    df_weekly = df.resample("W-MON").mean(numeric_only=True)
    df_weekly = df_weekly.dropna(how="all")

    # Forward-fill reproduction_rate and positive_rate (commonly delayed/missing)
    for col in ["reproduction_rate", "positive_rate"]:
        if col in df_weekly.columns:
            df_weekly[col] = df_weekly[col].interpolate(method="linear", limit=4)

    n = len(df_weekly)
    print(f"  Filtered: {country}, {n} weekly rows "
          f"({df_weekly.index[0].date()} → {df_weekly.index[-1].date()})")

    # ── ORI-C mapping ──────────────────────────────────────────────────────
    # O: inverse of normalised fatality burden (lower deaths → higher O)
    deaths = df_weekly["new_deaths_smoothed_per_million"].clip(lower=0).fillna(0)
    O = 1.0 - robust_minmax(deaths)

    # R: inverse of positive_rate (lower positivity → more resilient)
    if "positive_rate" in df_weekly.columns and df_weekly["positive_rate"].notna().sum() > 20:
        pos_rate = df_weekly["positive_rate"].clip(0, 1).fillna(method="ffill").fillna(0.1)
    else:
        # Proxy: deaths / cases ratio as positivity proxy
        pos_rate = (deaths / (df_weekly["new_cases_smoothed_per_million"].clip(lower=1) + 1e-9))
        pos_rate = pos_rate.clip(0, 1).fillna(0.1)
    R = 1.0 - robust_minmax(pos_rate)

    # I: 1 / (Rt + 0.1) normalised (lower Rt → more coherent containment)
    if "reproduction_rate" in df_weekly.columns and df_weekly["reproduction_rate"].notna().sum() > 20:
        rt = df_weekly["reproduction_rate"].clip(0.1, 5.0).fillna(method="ffill").fillna(1.5)
    else:
        # Estimate Rt from weekly case ratio
        cases = df_weekly["new_cases_smoothed_per_million"].clip(lower=0).fillna(0)
        cases_lag = cases.shift(1).clip(lower=1)
        rt = (cases / cases_lag).clip(0.1, 5.0).fillna(1.0)
    rt_inv = 1.0 / (rt + 0.1)
    I = robust_minmax(rt_inv)

    # S: vaccination coverage (0 → 1) — already cumulative
    if ("people_vaccinated_per_hundred" in df_weekly.columns
            and df_weekly["people_vaccinated_per_hundred"].notna().sum() > 5):
        vacc = df_weekly["people_vaccinated_per_hundred"].fillna(method="ffill").fillna(0)
        vacc = vacc.clip(0, 100) / 100.0
    else:
        vacc = pd.Series(np.linspace(0, 0.01, n), index=df_weekly.index)
    S = vacc.clip(0, 1)

    # demand: new_cases_per_million normalised
    cases_raw = df_weekly["new_cases_smoothed_per_million"].clip(lower=0).fillna(0)
    demand = robust_minmax(cases_raw)

    # ── Assemble output ────────────────────────────────────────────────────
    out = pd.DataFrame({
        "t":           range(n),
        "date":        df_weekly.index.strftime("%Y-%m-%d"),
        "O":           O.values,
        "R":           R.values,
        "I":           I.values,
        "S":           S.values,
        "demand":      demand.values,
        # Raw columns (kept for auditability)
        "new_cases_smoothed_per_million": cases_raw.values,
        "new_deaths_smoothed_per_million": deaths.values,
        "positive_rate_raw":   pos_rate.values,
        "reproduction_rate_raw": rt.values,
        "vaccination_per_hundred": (S.values * 100),
    })

    write_manifest(
        outdir / "fetch_manifest.json",
        sector="bio",
        pilot="epidemic",
        sources=[{"url": _OWID_URL, "sha256": sha, "country": country,
                  "license": "CC BY 4.0", "provider": "OurWorldInData"}],
        n_rows=n,
        date_range=(
            df_weekly.index[0].strftime("%Y-%m-%d"),
            df_weekly.index[-1].strftime("%Y-%m-%d"),
        ),
        notes=f"Weekly resampling (W-MON), country={country}, ORI-C normalised columns.",
    )

    return out


# ── Ecology (lynx + hare) ─────────────────────────────────────────────────────

def fetch_ecology(outdir: Path) -> pd.DataFrame:
    """
    Download Hudson Bay Company lynx + hare pelt records (1900–1920).
    Annual data → interpolated to monthly for ORI-C (n~240 months).
    """
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("\n[bio/ecology] Downloading lynx-hare dataset (Hudson Bay Co., 1900-1920)...")
    print("  Source: Elton & Nicholson (1942) / TidyTuesday — Public domain")

    # Try primary URL, then fallback
    data, used_url = None, None
    for url in [_LYNXHARE_URL, _LYNXHARE_FALLBACK_URL]:
        try:
            data = download_bytes(url)
            used_url = url
            break
        except RuntimeError as exc:
            print(f"  [warn] {url} failed: {exc}")

    if data is None:
        # Hardcode the classic dataset inline (21 years, public domain)
        print("  [warn] Both URLs failed — using inline canonical dataset (public domain)")
        data = _LYNXHARE_INLINE.encode()
        used_url = "inline_canonical"

    sha = sha256_bytes(data)
    raw_path = raw_dir / "lynxhare_raw.csv"
    raw_path.write_bytes(data)

    df_raw = pd.read_csv(io.BytesIO(data))
    print(f"  Raw columns: {list(df_raw.columns)}")

    # Normalise column names (different sources use different names)
    col_map: dict[str, str] = {}
    for c in df_raw.columns:
        cl = c.lower().strip()
        if "hare" in cl or "prey" in cl:
            col_map[c] = "hare"
        elif "lynx" in cl or "pred" in cl:
            col_map[c] = "lynx"
        elif "year" in cl or "time" in cl:
            col_map[c] = "year"
    df_raw = df_raw.rename(columns=col_map)

    if "year" not in df_raw.columns:
        df_raw = df_raw.rename(columns={df_raw.columns[0]: "year"})
    if "hare" not in df_raw.columns or "lynx" not in df_raw.columns:
        raise ValueError(f"Could not identify hare/lynx columns. Got: {list(df_raw.columns)}")

    df_raw = df_raw[["year", "hare", "lynx"]].dropna()
    df_raw["year"] = pd.to_numeric(df_raw["year"], errors="coerce")
    df_raw = df_raw.dropna().sort_values("year")

    # Interpolate annual → monthly (cubic spline)
    months = pd.date_range(
        start=f"{int(df_raw['year'].min())}-01",
        end=f"{int(df_raw['year'].max())}-12",
        freq="MS",
    )
    years_dec = df_raw["year"].values
    hare_ann  = df_raw["hare"].clip(lower=1).values
    lynx_ann  = df_raw["lynx"].clip(lower=1).values

    months_dec = months.year + (months.month - 1) / 12.0

    from scipy.interpolate import CubicSpline
    cs_hare = CubicSpline(years_dec, np.log(hare_ann))
    cs_lynx = CubicSpline(years_dec, np.log(lynx_ann))

    hare_m = np.exp(cs_hare(months_dec)).clip(min=0.01)
    lynx_m = np.exp(cs_lynx(months_dec)).clip(min=0.01)

    n = len(months)
    df_m = pd.DataFrame({"date": months, "hare": hare_m, "lynx": lynx_m})

    # ── ORI-C mapping ──────────────────────────────────────────────────────
    hare_s = pd.Series(hare_m, dtype=float)
    lynx_s = pd.Series(lynx_m, dtype=float)

    # O: prey (hare) density — food-web organisation
    O = robust_minmax(hare_s)

    # R: prey stability index — inverse rolling CV of hare
    W = 12
    rol_mean = hare_s.rolling(W, min_periods=4).mean()
    rol_std  = hare_s.rolling(W, min_periods=4).std().clip(lower=1e-3)
    cv_inv   = rol_mean / (rol_std + 1e-9)
    R = robust_minmax(cv_inv.fillna(method="bfill").fillna(1.0))

    # I: hare-lynx rolling correlation (integration / coupling)
    I_raw = rolling_corr(hare_s, lynx_s, window=24)
    I = I_raw.fillna(method="bfill").fillna(0.5)

    # S: cumulative biodiversity proxy — cumulative hare × lynx product norm
    product = hare_s * lynx_s
    S = cumsum_norm(robust_minmax(product), decay=0.003)

    # demand: predator-prey ratio (pressure from lynx on hare population)
    ratio = lynx_s / (hare_s + 1e-3)
    demand = robust_minmax(ratio)

    out = pd.DataFrame({
        "t":        range(n),
        "date":     months.strftime("%Y-%m"),
        "O":        O.values,
        "R":        R.values,
        "I":        I.values,
        "S":        S.values,
        "demand":   demand.values,
        "hare_raw": hare_m,
        "lynx_raw": lynx_m,
    })

    write_manifest(
        outdir / "fetch_manifest.json",
        sector="bio",
        pilot="ecology",
        sources=[{"url": used_url, "sha256": sha,
                  "license": "public domain",
                  "reference": "Elton & Nicholson (1942). The ten-year cycle in numbers of lynx."}],
        n_rows=n,
        date_range=(months[0].strftime("%Y-%m"), months[-1].strftime("%Y-%m")),
        notes="Annual Hudson Bay pelt counts interpolated to monthly (cubic spline, log-space).",
    )

    return out


# ── Inline lynx-hare canonical dataset (fallback, public domain) ──────────────
# Hudson Bay Company lynx-hare data 1900-1920 from Elton & Nicholson (1942)
_LYNXHARE_INLINE = """year,hare,lynx
1900,30000,4000
1901,47200,6100
1902,70200,9800
1903,77400,35200
1904,36300,59400
1905,20600,41700
1906,18100,19000
1907,21400,13000
1908,22000,8300
1909,25400,9100
1910,27100,7400
1911,40300,8000
1912,57000,12300
1913,76600,19500
1914,52300,45700
1915,19500,51100
1916,11200,29700
1917,7600,15800
1918,14600,9700
1919,16200,10100
1920,24700,8600
"""


# ── Proxy spec writers ────────────────────────────────────────────────────────

def _write_proxy_spec(outdir: Path, pilot: str) -> None:
    specs = {
        "epidemic": {
            "dataset_id":   "bio_epidemic_real",
            "sector":       "bio",
            "pilot":        "epidemic",
            "spec_version": "1.1",
            "data_type":    "real",
            "time_column":  "date",
            "time_mode":    "value",
            "normalization": "already_normalized",
            "data_source":  "OurWorldInData COVID-19 — CC BY 4.0",
            "data_url":     _OWID_URL,
            "columns": [
                {"oric_role": "O", "source_column": "O", "direction": "positive",
                 "fragility_score": 0.40,
                 "fragility_note": "Derived from deaths_per_million; reporting lag ~2 weeks",
                 "manipulability_note": "Death coding varies by country and period",
                 "description": "1 − deaths_per_million_norm: inverse fatality burden (organisation)"},
                {"oric_role": "R", "source_column": "R", "direction": "positive",
                 "fragility_score": 0.45,
                 "fragility_note": "Positivity rate depends on testing denominator consistency",
                 "manipulability_note": "Testing strategy changes create structural breaks",
                 "description": "1 − positive_rate_norm: fraction tested negative (resilience)"},
                {"oric_role": "I", "source_column": "I", "direction": "positive",
                 "fragility_score": 0.40,
                 "fragility_note": "Rt estimated from weekly case ratios; 7-14 day delay",
                 "manipulability_note": "Can be suppressed by reducing testing volume",
                 "description": "1/(Rt+0.1) norm: inverse effective reproduction number (integration)"},
                {"oric_role": "S", "source_column": "S", "direction": "positive",
                 "fragility_score": 0.30,
                 "fragility_note": "Coverage assumes homogeneous uptake; waning not reflected",
                 "manipulability_note": "Reported coverage may lag actual doses administered",
                 "description": "vaccination_coverage [0,1]: cumulative immune memory (symbolic stock)"},
                {"oric_role": "demand", "source_column": "demand", "direction": "positive",
                 "fragility_score": 0.35,
                 "fragility_note": "Cases under-reported in high-incidence phases",
                 "manipulability_note": "Reporting delays create apparent demand dips",
                 "description": "new_cases_smoothed_per_million norm: environmental demand"},
            ],
        },
        "ecology": {
            "dataset_id":   "bio_ecology_real",
            "sector":       "bio",
            "pilot":        "ecology",
            "spec_version": "1.1",
            "data_type":    "real",
            "time_column":  "date",
            "time_mode":    "value",
            "normalization": "already_normalized",
            "data_source":  "Elton & Nicholson (1942) — Public domain",
            "data_url":     _LYNXHARE_URL,
            "columns": [
                {"oric_role": "O", "source_column": "O", "direction": "positive",
                 "fragility_score": 0.40,
                 "fragility_note": "Pelt count is a proxy for population; trap effort not constant",
                 "manipulability_note": "Hudson Bay trading records; economic incentives affect count",
                 "description": "hare_norm: prey density (food-web organisation)"},
                {"oric_role": "R", "source_column": "R", "direction": "positive",
                 "fragility_score": 0.45,
                 "fragility_note": "Rolling CV sensitive to window size (pre-registered: 12 months)",
                 "manipulability_note": "Not manipulable; derived from count data",
                 "description": "Inverse rolling CV of hare population (resilience)"},
                {"oric_role": "I", "source_column": "I", "direction": "positive",
                 "fragility_score": 0.50,
                 "fragility_note": "Rolling correlation window pre-registered at 24 months",
                 "manipulability_note": "Not manipulable",
                 "description": "Hare-lynx rolling Pearson |r| (predator-prey coupling / integration)"},
                {"oric_role": "S", "source_column": "S", "direction": "positive",
                 "fragility_score": 0.45,
                 "fragility_note": "Cumulative product; decay parameter pre-registered at 0.003",
                 "manipulability_note": "Not manipulable",
                 "description": "Cumulative hare×lynx product (biodiversity interaction memory)"},
                {"oric_role": "demand", "source_column": "demand", "direction": "positive",
                 "fragility_score": 0.40,
                 "fragility_note": "Lynx/hare ratio is volatile near population crashes",
                 "manipulability_note": "Not manipulable",
                 "description": "Predator/prey ratio norm: predation pressure (environmental demand)"},
            ],
        },
    }
    spec_path = outdir / "proxy_spec.json"
    with open(spec_path, "w") as f:
        json.dump(specs[pilot], f, indent=2)
    print(f"  [proxy_spec] → {spec_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real bio sector data")
    parser.add_argument("--pilot",   choices=["epidemic", "ecology", "all"], default="all")
    parser.add_argument("--country", default="FRA", help="ISO code for epidemic pilot (default: FRA)")
    parser.add_argument("--outdir",  default=None,
                        help="Base output directory (default: 03_Data/sector_bio/real)")
    args = parser.parse_args()

    base = Path(args.outdir) if args.outdir else (REPO_ROOT / "03_Data/sector_bio/real")

    pilots = ["epidemic", "ecology"] if args.pilot == "all" else [args.pilot]

    for pilot in pilots:
        out = base / f"pilot_{pilot}"
        out.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  BIO / {pilot.upper()}")
        print(f"{'='*60}")
        try:
            if pilot == "epidemic":
                df = fetch_epidemic(out, country=args.country)
            else:
                df = fetch_ecology(out)

            save_real_csv(df, out / "real.csv")
            _write_proxy_spec(out, pilot)
            print(f"\n  ✓ {pilot}: {len(df)} rows → {out}/real.csv")
        except Exception as exc:
            print(f"\n  ✗ {pilot}: FAILED — {exc}")
            raise

    print("\nBio fetch complete.")


if __name__ == "__main__":
    main()
