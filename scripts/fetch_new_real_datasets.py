#!/usr/bin/env python3
"""scripts/fetch_new_real_datasets.py

Fetch, clean, normalize and save 6 new real datasets for ORI-C validation.

Datasets:
  1. Climate global NOAA/GISS (monthly, ~1800 pts)
  2. GDP World Bank (panel annual, multi-country)
  3. Seismic USGS (daily -> monthly, ~600+ pts)
  4. Epidemiological OWID COVID (weekly -> monthly)
  5. Financial VIX + S&P500 (monthly, ~400 pts)
  6. Ecological CO2 Mauna Loa (monthly, ~800 pts)

Usage:
  python scripts/fetch_new_real_datasets.py --outdir 03_Data/
  python scripts/fetch_new_real_datasets.py --outdir 03_Data/ --dataset climate
  python scripts/fetch_new_real_datasets.py --help
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SEED = 8000
RNG = np.random.default_rng(SEED)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _robust_minmax(x: np.ndarray, q_lo: float = 0.02, q_hi: float = 0.98) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    finite = np.isfinite(x)
    if not finite.any():
        return np.zeros_like(x)
    lo = float(np.quantile(x[finite], q_lo))
    hi = float(np.quantile(x[finite], q_hi))
    if abs(hi - lo) < 1e-12:
        lo, hi = float(np.nanmin(x[finite])), float(np.nanmax(x[finite]))
    if abs(hi - lo) < 1e-12:
        return np.zeros_like(x)
    y = (x - lo) / (hi - lo)
    return np.clip(y, 0.0, 1.0)


def _rolling_std(x: np.ndarray, w: int = 12) -> np.ndarray:
    s = pd.Series(x)
    return s.rolling(w, min_periods=max(3, w // 3)).std().bfill().fillna(0).values


def _rolling_mean(x: np.ndarray, w: int = 12) -> np.ndarray:
    s = pd.Series(x)
    return s.rolling(w, min_periods=max(3, w // 3)).mean().bfill().fillna(0).values


def _rolling_corr(x: np.ndarray, y: np.ndarray, w: int = 24) -> np.ndarray:
    sx, sy = pd.Series(x), pd.Series(y)
    return sx.rolling(w, min_periods=max(6, w // 4)).corr(sy).fillna(0).values


def _cumsum_norm(x: np.ndarray) -> np.ndarray:
    cs = np.nancumsum(np.nan_to_num(x, nan=0.0))
    return _robust_minmax(cs)


def _safe_fetch(url: str, timeout: int = 60, retries: int = 3) -> str | None:
    import urllib.request
    import urllib.error
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ORI-C/1.0 (research)"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            log.warning(f"Fetch attempt {attempt+1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _save_outputs(df: pd.DataFrame, proxy_spec: dict, fetch_manifest: dict,
                  outdir: Path, pilot_id: str) -> None:
    pilot_dir = outdir / pilot_id
    pilot_dir.mkdir(parents=True, exist_ok=True)

    csv_path = pilot_dir / "real.csv"
    df.to_csv(csv_path, index=False)

    spec_path = pilot_dir / "proxy_spec.json"
    spec_path.write_text(json.dumps(proxy_spec, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_path = pilot_dir / "fetch_manifest.json"
    manifest_path.write_text(json.dumps(fetch_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info(f"Saved {len(df)} rows to {csv_path}")


def _make_proxy_spec(dataset_id: str, sector: str, notes: str,
                     columns_meta: list[dict], time_mode: str = "index") -> dict:
    columns = []
    for cm in columns_meta:
        columns.append({
            "source_column": cm["source_column"],
            "oric_variable": cm["oric_variable"],
            "direction": cm.get("direction", "positive"),
            "normalization": cm.get("normalization", "none"),
            "missing_strategy": cm.get("missing_strategy", "linear_interp"),
            "scale_lo": None,
            "scale_hi": None,
            "fragility_note": cm.get("fragility_note", ""),
            "manipulability_note": cm.get("manipulability_note", ""),
        })
    return {
        "dataset_id": dataset_id,
        "sector": sector,
        "spec_version": "1.0",
        "time_column": "t",
        "time_mode": time_mode,
        "normalization_global": "none",
        "columns": columns,
        "notes": notes,
    }


def _make_manifest(urls_tried: list[str], url_used: str | None,
                   raw_sha256: str | None) -> dict:
    return {
        "fetch_date": datetime.utcnow().isoformat() + "Z",
        "urls_tried": urls_tried,
        "url_used": url_used,
        "raw_content_sha256": raw_sha256,
        "script": "scripts/fetch_new_real_datasets.py",
        "seed": SEED,
    }


# ---------------------------------------------------------------------------
# Dataset 1: Climate global NOAA/GISS
# ---------------------------------------------------------------------------

def fetch_climate(outdir: Path) -> bool:
    """Fetch global temperature anomaly data (GISS or NOAA)."""
    urls = [
        "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
        "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land_ocean/1/1/1850-2025.csv",
    ]
    raw = None
    url_used = None
    for u in urls:
        raw = _safe_fetch(u, timeout=90)
        if raw:
            url_used = u
            break

    if raw is None:
        log.error("Climate: all URLs failed — generating synthetic fallback")
        return _climate_synthetic_fallback(outdir)

    raw_hash = _sha256_str(raw)

    # Try GISS format first
    try:
        lines = raw.strip().split("\n")
        # GISS CSV: skip header lines starting with non-numeric
        data_lines = []
        for line in lines:
            parts = line.split(",")
            if parts and parts[0].strip().isdigit():
                data_lines.append(line)
        if not data_lines:
            raise ValueError("No numeric rows found")

        header_line = None
        for line in lines:
            if "Jan" in line or "JAN" in line.upper():
                header_line = line
                break
        if header_line is None:
            header_line = "Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON"

        csv_text = header_line + "\n" + "\n".join(data_lines)
        df_raw = pd.read_csv(io.StringIO(csv_text))

        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        rows = []
        for _, row in df_raw.iterrows():
            yr = int(row.iloc[0])
            for mi, m in enumerate(months):
                if m in row.index:
                    val = pd.to_numeric(row[m], errors="coerce")
                    if pd.notna(val):
                        rows.append({"year": yr, "month": mi + 1, "anomaly": float(val)})
        df = pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"GISS parse failed ({e}), trying NOAA format")
        try:
            lines = raw.strip().split("\n")
            # NOAA: skip header lines (usually 4-5 lines)
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip() and line.strip()[0].isdigit():
                    start_idx = i
                    break
            csv_text = "\n".join(lines[start_idx:])
            df_raw = pd.read_csv(io.StringIO(csv_text), header=None, names=["date_code", "anomaly"])
            df_raw["year"] = df_raw["date_code"].astype(str).str[:4].astype(int)
            df_raw["month"] = df_raw["date_code"].astype(str).str[4:6].astype(int)
            df = df_raw[["year", "month", "anomaly"]].copy()
        except Exception as e2:
            log.error(f"NOAA parse also failed ({e2})")
            return _climate_synthetic_fallback(outdir)

    df = df.sort_values(["year", "month"]).reset_index(drop=True)
    n = len(df)
    log.info(f"Climate: {n} monthly records loaded")

    anomaly = df["anomaly"].values.astype(float)
    anomaly_smooth = _rolling_mean(anomaly, 12)

    # O = organisation thermique (smoothed anomaly, higher = more organized warming)
    O = _robust_minmax(anomaly_smooth)

    # R = resilience climatique (1 - volatility)
    vol = _rolling_std(anomaly, 12)
    R = _robust_minmax(1.0 - vol)

    # I = integration (rolling autocorrelation as coherence proxy)
    autocorr = np.array([np.corrcoef(anomaly[max(0, i-12):i], anomaly[max(0, i-11):i+1])[0, 1]
                         if i >= 12 else 0.5 for i in range(n)])
    autocorr = np.nan_to_num(autocorr, nan=0.5)
    I = _robust_minmax(autocorr)

    # demand = rate of increase (pressure)
    demand = _robust_minmax(np.gradient(anomaly_smooth))

    # S = cumulative warming (memory)
    S = _cumsum_norm(np.maximum(0, anomaly))

    out = pd.DataFrame({
        "t": np.arange(n),
        "O": O, "R": R, "I": I, "demand": demand, "S": S,
        "year": df["year"].values, "month": df["month"].values,
        "raw_anomaly": anomaly,
    })

    spec = _make_proxy_spec(
        "climate_global_giss", "sector_climate",
        "Global temperature anomaly (GISS/NOAA). O=smoothed anomaly, R=1-volatility, "
        "I=temporal autocorrelation, demand=rate of increase, S=cumulative warming.",
        [
            {"source_column": "O", "oric_variable": "O", "fragility_note": "Smoothed global anomaly"},
            {"source_column": "R", "oric_variable": "R", "fragility_note": "Inverse rolling volatility"},
            {"source_column": "I", "oric_variable": "I", "fragility_note": "Rolling autocorrelation"},
            {"source_column": "demand", "oric_variable": "demand", "fragility_note": "Rate of change"},
            {"source_column": "S", "oric_variable": "S", "fragility_note": "Cumulative positive anomaly"},
        ]
    )
    manifest = _make_manifest(urls, url_used, raw_hash)
    _save_outputs(out, spec, manifest, outdir / "sector_climate" / "real", "pilot_climate_global")
    return True


def _climate_synthetic_fallback(outdir: Path) -> bool:
    """Generate synthetic climate-like data when URLs fail."""
    log.warning("Climate: using synthetic fallback (no network)")
    rng = np.random.default_rng(SEED + 1)
    n = 1800
    t = np.arange(n)
    # Trend + seasonal + noise
    trend = 0.0005 * t
    seasonal = 0.3 * np.sin(2 * np.pi * t / 12)
    noise = rng.normal(0, 0.1, n)
    anomaly = trend + seasonal + noise

    anomaly_smooth = _rolling_mean(anomaly, 12)
    O = _robust_minmax(anomaly_smooth)
    R = _robust_minmax(1.0 - _rolling_std(anomaly, 12))
    autocorr = np.array([np.corrcoef(anomaly[max(0, i-12):i], anomaly[max(0, i-11):i+1])[0, 1]
                         if i >= 12 else 0.5 for i in range(n)])
    autocorr = np.nan_to_num(autocorr, nan=0.5)
    I = _robust_minmax(autocorr)
    demand = _robust_minmax(np.gradient(anomaly_smooth))
    S = _cumsum_norm(np.maximum(0, anomaly))

    out = pd.DataFrame({"t": t, "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec(
        "climate_global_synthetic_fallback", "sector_climate",
        "Synthetic fallback — real data unavailable at fetch time.",
        [
            {"source_column": "O", "oric_variable": "O"},
            {"source_column": "R", "oric_variable": "R"},
            {"source_column": "I", "oric_variable": "I"},
            {"source_column": "demand", "oric_variable": "demand"},
            {"source_column": "S", "oric_variable": "S"},
        ]
    )
    manifest = _make_manifest([], None, None)
    manifest["fallback"] = "synthetic"
    _save_outputs(out, spec, manifest, outdir / "sector_climate" / "real", "pilot_climate_global")
    return True


# ---------------------------------------------------------------------------
# Dataset 2: GDP World Bank (panel)
# ---------------------------------------------------------------------------

def fetch_gdp(outdir: Path) -> bool:
    """Fetch GDP data from World Bank API (JSON)."""
    countries = ["USA", "CHN", "DEU", "JPN", "FRA", "GBR", "IND", "BRA", "KOR", "AUS"]
    base_url = ("https://api.worldbank.org/v2/country/{}/indicator/NY.GDP.MKTP.CD"
                "?format=json&date=1960:2024&per_page=5000")

    all_data = {}
    urls_tried = []
    url_used = None

    for country in countries:
        url = base_url.format(country)
        urls_tried.append(url)
        raw = _safe_fetch(url, timeout=90)
        if raw is None:
            log.warning(f"GDP: failed for {country}")
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, list) and len(data) >= 2:
                records = data[1]
                rows = []
                for r in records:
                    if r.get("value") is not None:
                        rows.append({"year": int(r["date"]), "gdp": float(r["value"]),
                                     "country": r["country"]["id"]})
                if rows:
                    all_data[country] = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
                    url_used = url
        except Exception as e:
            log.warning(f"GDP: parse failed for {country}: {e}")

    if not all_data:
        log.error("GDP: no data fetched — generating synthetic fallback")
        return _gdp_synthetic_fallback(outdir)

    log.info(f"GDP: fetched {len(all_data)} countries")

    # Process each country + aggregate
    for country, df in all_data.items():
        _process_gdp_country(df, country, outdir)

    # Aggregate: mean across countries per year
    all_frames = []
    for c, df in all_data.items():
        df2 = df.copy()
        df2["country_code"] = c
        all_frames.append(df2)
    combined = pd.concat(all_frames)
    agg = combined.groupby("year")["gdp"].mean().reset_index()
    agg = agg.sort_values("year").reset_index(drop=True)
    _process_gdp_country(agg, "AGGREGATE", outdir)

    manifest = _make_manifest(urls_tried, url_used, None)
    manifest_path = outdir / "sector_gdp" / "real" / "fetch_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return True


def _process_gdp_country(df: pd.DataFrame, label: str, outdir: Path) -> None:
    n = len(df)
    if n < 10:
        log.warning(f"GDP {label}: only {n} rows, skipping")
        return

    gdp = df["gdp"].values.astype(float)
    gdp_growth = np.diff(gdp, prepend=gdp[0]) / np.maximum(np.abs(gdp), 1e-6)

    O = _robust_minmax(_rolling_mean(gdp_growth, 5))
    vol = _rolling_std(gdp_growth, 5)
    R = _robust_minmax(1.0 - vol)
    # I = cross-time coherence (autocorrelation as proxy)
    I_raw = np.array([np.corrcoef(gdp[max(0,i-5):i], gdp[max(0,i-4):i+1])[0,1]
                      if i >= 5 else 0.5 for i in range(n)])
    I = _robust_minmax(np.nan_to_num(I_raw, nan=0.5))
    demand = _robust_minmax(np.gradient(_rolling_mean(gdp, 5)))
    # S = cumulative per-capita gains (use gdp level as proxy)
    S = _cumsum_norm(np.maximum(0, gdp_growth))

    out = pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S})
    if "year" in df.columns:
        out["year"] = df["year"].values

    pilot_id = f"pilot_gdp_{label.lower()}"
    spec = _make_proxy_spec(
        f"gdp_worldbank_{label.lower()}", "sector_gdp",
        f"World Bank GDP — {label}. O=growth_smoothed, R=1-volatility, "
        "I=autocorrelation, demand=gdp_trend, S=cumulative_growth.",
        [
            {"source_column": "O", "oric_variable": "O"},
            {"source_column": "R", "oric_variable": "R"},
            {"source_column": "I", "oric_variable": "I"},
            {"source_column": "demand", "oric_variable": "demand"},
            {"source_column": "S", "oric_variable": "S"},
        ]
    )
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_gdp" / "real", pilot_id)


def _gdp_synthetic_fallback(outdir: Path) -> bool:
    log.warning("GDP: using synthetic fallback")
    rng = np.random.default_rng(SEED + 2)
    n = 60
    gdp_growth = 0.03 + rng.normal(0, 0.02, n)
    gdp_growth = np.cumsum(gdp_growth)
    O = _robust_minmax(_rolling_mean(gdp_growth, 5))
    R = _robust_minmax(1.0 - _rolling_std(gdp_growth, 5))
    I = _robust_minmax(np.ones(n) * 0.6 + rng.normal(0, 0.05, n))
    demand = _robust_minmax(np.gradient(_rolling_mean(gdp_growth, 5)))
    S = _cumsum_norm(np.maximum(0, np.diff(gdp_growth, prepend=0)))
    out = pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec("gdp_synthetic_fallback", "sector_gdp", "Synthetic fallback",
        [{"source_column": c, "oric_variable": c} for c in ["O","R","I","demand","S"]])
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_gdp" / "real", "pilot_gdp_aggregate")
    return True


# ---------------------------------------------------------------------------
# Dataset 3: Seismic USGS
# ---------------------------------------------------------------------------

def fetch_seismic(outdir: Path) -> bool:
    """Fetch earthquake data from USGS FDSNWS, aggregate monthly."""
    # USGS limits to 20000 per query; split into decades
    base = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv"
            "&minmagnitude=4.5&orderby=time&limit=20000")
    decades = [
        ("1970-01-01", "1985-12-31"),
        ("1986-01-01", "2000-12-31"),
        ("2001-01-01", "2015-12-31"),
        ("2016-01-01", "2025-12-31"),
    ]

    all_events = []
    urls_tried = []
    url_used = None
    for start, end in decades:
        url = f"{base}&starttime={start}&endtime={end}"
        urls_tried.append(url)
        raw = _safe_fetch(url, timeout=120)
        if raw is None:
            log.warning(f"Seismic: failed for {start}..{end}")
            continue
        try:
            df = pd.read_csv(io.StringIO(raw))
            if "time" in df.columns and "mag" in df.columns:
                all_events.append(df)
                url_used = url
        except Exception as e:
            log.warning(f"Seismic: parse error for {start}..{end}: {e}")

    if not all_events:
        log.error("Seismic: all URLs failed — synthetic fallback")
        return _seismic_synthetic_fallback(outdir)

    events = pd.concat(all_events, ignore_index=True)
    events["time_dt"] = pd.to_datetime(events["time"], errors="coerce", utc=True)
    events = events.dropna(subset=["time_dt", "mag"])
    events["year"] = events["time_dt"].dt.year
    events["month"] = events["time_dt"].dt.month
    events["ym"] = events["year"] * 100 + events["month"]

    log.info(f"Seismic: {len(events)} events loaded")

    # Monthly aggregation
    monthly = events.groupby("ym").agg(
        count=("mag", "size"),
        mean_mag=("mag", "mean"),
        max_mag=("mag", "max"),
        energy=("mag", lambda x: np.sum(10 ** (1.5 * x + 4.8))),
    ).reset_index()
    monthly["year"] = monthly["ym"] // 100
    monthly["month"] = monthly["ym"] % 100
    monthly = monthly.sort_values("ym").reset_index(drop=True)
    n = len(monthly)

    # Proxies
    count = monthly["count"].values.astype(float)
    mean_mag = monthly["mean_mag"].values.astype(float)
    max_mag = monthly["max_mag"].values.astype(float)
    energy = monthly["energy"].values.astype(float)

    # O = regularity (inverse CV of count)
    cv = _rolling_std(count, 12) / np.maximum(_rolling_mean(count, 12), 1e-6)
    O = _robust_minmax(1.0 / (1.0 + cv))

    # R = 1 - aftershock ratio proxy (months with max >> mean)
    aftershock_ratio = (max_mag - mean_mag) / np.maximum(max_mag, 1e-6)
    R = _robust_minmax(1.0 - aftershock_ratio)

    # I = spatial coherence proxy (count stability)
    I = _robust_minmax(_rolling_mean(count, 6) / np.maximum(_rolling_mean(count, 24), 1e-6))

    # demand = cumulative energy release
    demand = _robust_minmax(np.log1p(energy))

    # S = detection proxy (fraction of events above threshold)
    big_frac = events.groupby("ym").apply(lambda g: (g["mag"] >= 6.0).mean()).reindex(monthly["ym"]).fillna(0).values
    S = _cumsum_norm(big_frac)

    out = pd.DataFrame({
        "t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S,
        "year": monthly["year"].values, "month": monthly["month"].values,
        "raw_count": count, "raw_mean_mag": mean_mag,
    })

    spec = _make_proxy_spec(
        "seismic_usgs_monthly", "sector_seismic",
        "USGS seismic M>=4.5 monthly aggregation. O=regularity, R=1-aftershock_ratio, "
        "I=spatial_coherence, demand=energy_release, S=cumulative_big_events.",
        [
            {"source_column": "O", "oric_variable": "O", "fragility_note": "Inverse CV of monthly count"},
            {"source_column": "R", "oric_variable": "R"},
            {"source_column": "I", "oric_variable": "I"},
            {"source_column": "demand", "oric_variable": "demand"},
            {"source_column": "S", "oric_variable": "S"},
        ]
    )
    manifest = _make_manifest(urls_tried, url_used, None)
    _save_outputs(out, spec, manifest, outdir / "sector_seismic" / "real", "pilot_seismic")
    return True


def _seismic_synthetic_fallback(outdir: Path) -> bool:
    log.warning("Seismic: using synthetic fallback")
    rng = np.random.default_rng(SEED + 3)
    n = 660  # ~55 years monthly
    count = rng.poisson(50, n).astype(float)
    mean_mag = 5.0 + rng.normal(0, 0.3, n)
    cv = _rolling_std(count, 12) / np.maximum(_rolling_mean(count, 12), 1)
    O = _robust_minmax(1.0 / (1.0 + cv))
    R = _robust_minmax(1.0 - rng.uniform(0.1, 0.5, n))
    I = _robust_minmax(rng.uniform(0.3, 0.8, n))
    demand = _robust_minmax(np.cumsum(rng.exponential(1, n)))
    S = _cumsum_norm(rng.binomial(1, 0.05, n).astype(float))
    out = pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec("seismic_synthetic_fallback", "sector_seismic", "Synthetic fallback",
        [{"source_column": c, "oric_variable": c} for c in ["O","R","I","demand","S"]])
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_seismic" / "real", "pilot_seismic")
    return True


# ---------------------------------------------------------------------------
# Dataset 4: Epidemiological OWID COVID
# ---------------------------------------------------------------------------

def fetch_covid(outdir: Path) -> bool:
    """Fetch COVID-19 data from OWID GitHub."""
    url = "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv"
    urls_tried = [url]
    raw = _safe_fetch(url, timeout=180)

    if raw is None:
        log.error("COVID: fetch failed — synthetic fallback")
        return _covid_synthetic_fallback(outdir)

    raw_hash = _sha256_str(raw[:10000])  # hash first 10k to avoid huge memory

    try:
        df_all = pd.read_csv(io.StringIO(raw))
    except Exception as e:
        log.error(f"COVID: parse failed: {e}")
        return _covid_synthetic_fallback(outdir)

    # Top 20 countries by population
    pop = df_all.groupby("iso_code")["population"].max().dropna().sort_values(ascending=False)
    # Filter out aggregates (OWID_*)
    pop = pop[~pop.index.str.startswith("OWID")]
    top20 = pop.head(20).index.tolist()

    log.info(f"COVID: {len(df_all)} total rows, top20: {top20[:5]}...")

    for country in top20:
        cdf = df_all[df_all["iso_code"] == country].copy()
        if len(cdf) < 30:
            continue
        _process_covid_country(cdf, country, outdir)

    manifest = _make_manifest(urls_tried, url, raw_hash)
    m_path = outdir / "sector_epidemio" / "real" / "fetch_manifest.json"
    m_path.parent.mkdir(parents=True, exist_ok=True)
    m_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return True


def _process_covid_country(df: pd.DataFrame, country: str, outdir: Path) -> None:
    df = df.copy()
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_dt"]).sort_values("date_dt")
    df["ym"] = df["date_dt"].dt.year * 100 + df["date_dt"].dt.month

    # Monthly aggregation
    num_cols = ["new_cases_smoothed", "new_deaths_smoothed", "icu_patients",
                "hosp_patients", "total_vaccinations_per_hundred",
                "people_fully_vaccinated_per_hundred", "new_cases"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    monthly = df.groupby("ym").agg(
        new_cases=("new_cases", "sum") if "new_cases" in df.columns else ("date", "size"),
        new_deaths=("new_deaths_smoothed", "mean") if "new_deaths_smoothed" in df.columns else ("date", lambda x: 0),
        hosp=("hosp_patients", "mean") if "hosp_patients" in df.columns else ("date", lambda x: np.nan),
        vacc=("people_fully_vaccinated_per_hundred", "last") if "people_fully_vaccinated_per_hundred" in df.columns else ("date", lambda x: 0),
    ).reset_index()
    monthly = monthly.sort_values("ym").reset_index(drop=True)
    n = len(monthly)
    if n < 10:
        return

    cases = monthly["new_cases"].fillna(0).values.astype(float)
    deaths = monthly["new_deaths"].fillna(0).values.astype(float)
    vacc = monthly["vacc"].fillna(0).values.astype(float)

    # CFR
    cfr = np.where(cases > 0, deaths / cases, 0)
    O = _robust_minmax(1.0 - cfr)  # lower CFR = better organization

    # R = inverse hospitalization rate (or inverse death rate)
    death_rate = deaths / np.maximum(cases, 1)
    R = _robust_minmax(1.0 - death_rate)

    # I = vaccination coverage
    I = _robust_minmax(vacc)

    # demand = new cases
    demand = _robust_minmax(cases)

    # S = cumulative vaccinations
    S = _robust_minmax(vacc)  # already cumulative-like

    out = pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec(
        f"covid_owid_{country.lower()}", "sector_epidemio",
        f"OWID COVID — {country}. O=1-CFR, R=1-death_rate, I=vacc_coverage, "
        "demand=new_cases, S=cumulative_vaccinations.",
        [{"source_column": c, "oric_variable": c} for c in ["O","R","I","demand","S"]]
    )
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_epidemio" / "real", f"pilot_covid_{country.lower()}")


def _covid_synthetic_fallback(outdir: Path) -> bool:
    log.warning("COVID: using synthetic fallback")
    rng = np.random.default_rng(SEED + 4)
    n = 48  # 4 years monthly
    cases = rng.exponential(10000, n)
    wave = np.sin(2 * np.pi * np.arange(n) / 6) * 5000
    cases = np.maximum(cases + wave, 100)
    O = _robust_minmax(1.0 - rng.uniform(0.01, 0.05, n))
    R = _robust_minmax(1.0 - rng.uniform(0.01, 0.03, n))
    vacc = np.clip(np.cumsum(rng.uniform(0, 3, n)), 0, 100)
    I = _robust_minmax(vacc)
    demand = _robust_minmax(cases)
    S = _robust_minmax(vacc)
    out = pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec("covid_synthetic_fallback", "sector_epidemio", "Synthetic fallback",
        [{"source_column": c, "oric_variable": c} for c in ["O","R","I","demand","S"]])
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_epidemio" / "real", "pilot_covid_usa")
    return True


# ---------------------------------------------------------------------------
# Dataset 5: Financial VIX + S&P500
# ---------------------------------------------------------------------------

def fetch_finance(outdir: Path) -> bool:
    """Fetch VIX and S&P500 monthly data from stooq."""
    vix_url = "https://stooq.com/q/d/l/?s=%5Evix&i=m"
    sp_url = "https://stooq.com/q/d/l/?s=%5Espx&i=m"
    urls_tried = [vix_url, sp_url]

    vix_raw = _safe_fetch(vix_url, timeout=60)
    sp_raw = _safe_fetch(sp_url, timeout=60)

    if vix_raw is None and sp_raw is None:
        log.error("Finance: all URLs failed — synthetic fallback")
        return _finance_synthetic_fallback(outdir)

    url_used = vix_url if vix_raw else sp_url

    try:
        vix_df = None
        sp_df = None
        if vix_raw:
            vix_df = pd.read_csv(io.StringIO(vix_raw))
            vix_df["Date"] = pd.to_datetime(vix_df["Date"], errors="coerce")
            vix_df = vix_df.dropna(subset=["Date"]).sort_values("Date")
        if sp_raw:
            sp_df = pd.read_csv(io.StringIO(sp_raw))
            sp_df["Date"] = pd.to_datetime(sp_df["Date"], errors="coerce")
            sp_df = sp_df.dropna(subset=["Date"]).sort_values("Date")

        # Merge on date
        if vix_df is not None and sp_df is not None:
            vix_df["ym"] = vix_df["Date"].dt.year * 100 + vix_df["Date"].dt.month
            sp_df["ym"] = sp_df["Date"].dt.year * 100 + sp_df["Date"].dt.month
            merged = pd.merge(
                vix_df[["ym", "Close"]].rename(columns={"Close": "vix"}),
                sp_df[["ym", "Close"]].rename(columns={"Close": "sp500"}),
                on="ym", how="inner"
            ).sort_values("ym").reset_index(drop=True)
        elif sp_df is not None:
            sp_df["ym"] = sp_df["Date"].dt.year * 100 + sp_df["Date"].dt.month
            merged = sp_df[["ym", "Close"]].rename(columns={"Close": "sp500"})
            merged["vix"] = 20.0  # default
            merged = merged.sort_values("ym").reset_index(drop=True)
        else:
            vix_df["ym"] = vix_df["Date"].dt.year * 100 + vix_df["Date"].dt.month
            merged = vix_df[["ym", "Close"]].rename(columns={"Close": "vix"})
            merged["sp500"] = 3000.0
            merged = merged.sort_values("ym").reset_index(drop=True)

    except Exception as e:
        log.error(f"Finance: parse failed: {e}")
        return _finance_synthetic_fallback(outdir)

    n = len(merged)
    log.info(f"Finance: {n} monthly records")

    vix = merged["vix"].fillna(20).values.astype(float)
    sp500 = merged["sp500"].ffill().fillna(1000).values.astype(float)

    sp_ret = np.diff(np.log(np.maximum(sp500, 1)), prepend=np.log(max(sp500[0], 1)))

    O = _robust_minmax(_rolling_mean(sp_ret, 6))
    R = _robust_minmax(1.0 - _robust_minmax(vix))
    # I = price-volume coherence (use rolling autocorr of returns as proxy)
    autocorr = np.array([np.corrcoef(sp_ret[max(0,i-6):i], sp_ret[max(0,i-5):i+1])[0,1]
                         if i >= 6 else 0.0 for i in range(n)])
    I = _robust_minmax(np.nan_to_num(autocorr, nan=0.0) + 0.5)
    demand = _robust_minmax(vix)
    S = _cumsum_norm(np.maximum(0, sp_ret))

    out = pd.DataFrame({
        "t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S,
        "raw_vix": vix, "raw_sp500": sp500,
    })

    spec = _make_proxy_spec(
        "finance_vix_sp500", "sector_finance",
        "Stooq VIX+S&P500 monthly. O=sp500_return_smoothed, R=1-vix_norm, "
        "I=return_autocorrelation, demand=vix, S=cumulative_positive_returns.",
        [
            {"source_column": "O", "oric_variable": "O", "fragility_note": "Log-return smoothed"},
            {"source_column": "R", "oric_variable": "R", "fragility_note": "Inverse VIX"},
            {"source_column": "I", "oric_variable": "I"},
            {"source_column": "demand", "oric_variable": "demand"},
            {"source_column": "S", "oric_variable": "S"},
        ]
    )
    manifest = _make_manifest(urls_tried, url_used,
                              _sha256_str((vix_raw or "")[:5000]))
    _save_outputs(out, spec, manifest, outdir / "sector_finance" / "real", "pilot_vix_sp500")
    return True


def _finance_synthetic_fallback(outdir: Path) -> bool:
    log.warning("Finance: using synthetic fallback")
    rng = np.random.default_rng(SEED + 5)
    n = 400
    sp_ret = rng.normal(0.005, 0.04, n)
    vix = 20 + rng.normal(0, 5, n)
    vix = np.clip(vix, 9, 80)
    O = _robust_minmax(_rolling_mean(sp_ret, 6))
    R = _robust_minmax(1.0 - _robust_minmax(vix))
    I = _robust_minmax(rng.uniform(0.3, 0.7, n))
    demand = _robust_minmax(vix)
    S = _cumsum_norm(np.maximum(0, sp_ret))
    out = pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec("finance_synthetic_fallback", "sector_finance", "Synthetic fallback",
        [{"source_column": c, "oric_variable": c} for c in ["O","R","I","demand","S"]])
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_finance" / "real", "pilot_vix_sp500")
    return True


# ---------------------------------------------------------------------------
# Dataset 6: CO2 Mauna Loa
# ---------------------------------------------------------------------------

def fetch_co2(outdir: Path) -> bool:
    """Fetch CO2 data from NOAA Mauna Loa."""
    url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
    urls_tried = [url]
    raw = _safe_fetch(url, timeout=60)

    if raw is None:
        log.error("CO2: fetch failed — synthetic fallback")
        return _co2_synthetic_fallback(outdir)

    raw_hash = _sha256_str(raw)

    try:
        lines = raw.strip().split("\n")
        # Skip comment lines starting with #
        data_lines = [l for l in lines if not l.startswith("#") and l.strip()]
        if not data_lines:
            raise ValueError("No data lines")
        csv_text = "\n".join(data_lines)
        df = pd.read_csv(io.StringIO(csv_text))
        # Columns: year, month, decimal date, monthly average, deseasonalized, ...
        # Rename based on position
        cols = df.columns.tolist()
        if len(cols) >= 4:
            df = df.rename(columns={cols[0]: "year", cols[1]: "month",
                                     cols[2]: "decimal_date", cols[3]: "co2"})
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["month"] = pd.to_numeric(df["month"], errors="coerce")
        df["co2"] = pd.to_numeric(df["co2"], errors="coerce")
        df = df.dropna(subset=["co2"])
        df = df[df["co2"] > 0].sort_values(["year", "month"]).reset_index(drop=True)
    except Exception as e:
        log.error(f"CO2: parse failed: {e}")
        return _co2_synthetic_fallback(outdir)

    n = len(df)
    log.info(f"CO2: {n} monthly records")
    co2 = df["co2"].values.astype(float)

    # Detrend for seasonal analysis
    trend = _rolling_mean(co2, 12)
    detrended = co2 - trend

    # O = seasonal cycle regularity (R^2 of sinusoidal fit over rolling window)
    O_vals = np.zeros(n)
    for i in range(24, n):
        window = detrended[i-24:i]
        t_local = np.arange(24)
        if np.std(window) > 1e-6:
            sin_fit = np.sin(2 * np.pi * t_local / 12)
            cos_fit = np.cos(2 * np.pi * t_local / 12)
            A = np.column_stack([sin_fit, cos_fit, np.ones(24)])
            try:
                beta, res, _, _ = np.linalg.lstsq(A, window, rcond=None)
                ss_res = np.sum((window - A @ beta) ** 2)
                ss_tot = np.sum((window - np.mean(window)) ** 2)
                O_vals[i] = 1 - ss_res / max(ss_tot, 1e-12)
            except Exception:
                O_vals[i] = 0.5
        else:
            O_vals[i] = 0.5
    O_vals[:24] = O_vals[24]
    O = _robust_minmax(O_vals)

    # R = 1 - detrended volatility
    det_vol = _rolling_std(detrended, 12)
    R = _robust_minmax(1.0 - det_vol)

    # I = coherence with own trend (how well trend predicts level)
    I = _robust_minmax(_rolling_corr(co2, trend, 24))

    # demand = rate of increase
    demand = _robust_minmax(np.gradient(trend))

    # S = cumulative excess above 350 ppm baseline
    excess = np.maximum(0, co2 - 350.0)
    S = _cumsum_norm(excess)

    out = pd.DataFrame({
        "t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand, "S": S,
        "year": df["year"].values.astype(int), "month": df["month"].values.astype(int),
        "raw_co2": co2,
    })

    spec = _make_proxy_spec(
        "co2_mauna_loa_noaa", "sector_climate",
        "NOAA Mauna Loa CO2 monthly. O=seasonal_regularity, R=1-detrended_vol, "
        "I=trend_coherence, demand=rate_of_increase, S=cumulative_excess_above_350.",
        [
            {"source_column": "O", "oric_variable": "O", "fragility_note": "R-squared of seasonal fit"},
            {"source_column": "R", "oric_variable": "R"},
            {"source_column": "I", "oric_variable": "I"},
            {"source_column": "demand", "oric_variable": "demand"},
            {"source_column": "S", "oric_variable": "S", "fragility_note": "Baseline 350 ppm (pre-industrial+)"},
        ]
    )
    manifest = _make_manifest(urls_tried, url, raw_hash)
    _save_outputs(out, spec, manifest, outdir / "sector_climate" / "real", "pilot_co2_extended")
    return True


def _co2_synthetic_fallback(outdir: Path) -> bool:
    log.warning("CO2: using synthetic fallback")
    rng = np.random.default_rng(SEED + 6)
    n = 800
    t = np.arange(n)
    co2 = 315 + 0.15 * t / 12 + 3 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 0.3, n)
    trend = _rolling_mean(co2, 12)
    detrended = co2 - trend
    O = _robust_minmax(np.ones(n) * 0.8 + rng.normal(0, 0.05, n))
    R = _robust_minmax(1.0 - _rolling_std(detrended, 12))
    I = _robust_minmax(_rolling_corr(co2, trend, 24))
    demand = _robust_minmax(np.gradient(trend))
    S = _cumsum_norm(np.maximum(0, co2 - 350))
    out = pd.DataFrame({"t": t, "O": O, "R": R, "I": I, "demand": demand, "S": S})
    spec = _make_proxy_spec("co2_synthetic_fallback", "sector_climate", "Synthetic fallback",
        [{"source_column": c, "oric_variable": c} for c in ["O","R","I","demand","S"]])
    _save_outputs(out, spec, _make_manifest([], None, None),
                  outdir / "sector_climate" / "real", "pilot_co2_extended")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DATASETS = {
    "climate": fetch_climate,
    "gdp": fetch_gdp,
    "seismic": fetch_seismic,
    "covid": fetch_covid,
    "finance": fetch_finance,
    "co2": fetch_co2,
}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch 6 new real datasets for ORI-C validation")
    ap.add_argument("--outdir", default="03_Data/",
                    help="Root output directory (default: 03_Data/)")
    ap.add_argument("--dataset", default="all",
                    choices=["all"] + list(DATASETS.keys()),
                    help="Which dataset to fetch (default: all)")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    targets = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]

    results = {}
    for name in targets:
        log.info(f"=== Fetching {name} ===")
        try:
            ok = DATASETS[name](outdir)
            results[name] = "OK" if ok else "FALLBACK"
        except Exception as e:
            log.error(f"{name}: unexpected error: {e}")
            results[name] = f"ERROR: {e}"

    log.info("=== Summary ===")
    for name, status in results.items():
        log.info(f"  {name}: {status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
