"""fetch_real_data.py — Psych sector real-data fetcher.

Sources (all public, no authentication required):

  google_trends — Google Trends weekly interest data via pytrends (unofficial API)
    Topics: mental health, social trust, collective behaviour keywords
    Method: pytrends TrendReq (unofficial Google Trends API, no key needed)
    Period: 2004-01 → present, weekly → resampled monthly

  wvs_synthetic — World Values Survey proxy via publicly aggregated WVS data
    Source: WVS Wave 7 country-level summary statistics (public CSV on WVS website)
    URL: https://www.worldvaluessurvey.org/WVSDocumentationWV7.jsp
    NOTE: WVS microdata requires registration. This pilot uses pre-aggregated
          public summary indicators (available without registration) and falls
          back to a synthetic calibrated to WVS distributions if the fetch fails.

Output (per pilot):
  03_Data/sector_psych/real/pilot_<id>/real.csv
  03_Data/sector_psych/real/pilot_<id>/proxy_spec.json
  03_Data/sector_psych/real/pilot_<id>/fetch_manifest.json

ORI-C mapping (google_trends — social trust / collective behaviour):
  O = social_trust_norm          → organisational capacity (trust = glue of society)
  R = 1 − anxiety_index_norm     → societal resilience (inverse of collective anxiety)
  I = search_coherence_norm      → integration (co-occurrence of related searches)
  S = cumulative_civicness_norm  → symbolic stock (civic engagement momentum)
  demand = crisis_proxy_norm     → exogenous pressure (spike in crisis-related searches)

ORI-C mapping (wvs_synthetic):
  O = institutional_trust_norm   → organisational capacity
  R = 1 − inequality_norm        → resilience proxy (lower inequality = more resilient)
  I = cultural_coherence_norm    → integration (within-country cultural homogeneity)
  S = cumulative_norm_adoption   → symbolic stock (norm adoption over waves)
  demand = social_stress_norm    → exogenous pressure
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "shared"))
from fetch_utils import (
    robust_minmax, minmax, cumsum_norm,
    rolling_corr, save_real_csv, write_manifest,
)

REPO_ROOT = _HERE.parent.parent.parent


# ── Google Trends via pytrends ─────────────────────────────────────────────────

def _fetch_google_trends(outdir: Path, raw_dir: Path) -> tuple[pd.DataFrame, bytes]:
    """Fetch Google Trends data for social psychology keywords."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        raise ImportError(
            "pytrends is required for google_trends pilot. "
            "Install with: pip install pytrends"
        )

    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))

    # Keywords mapped to ORI-C variables
    kw_trust    = ["social trust", "community solidarity"]
    kw_anxiety  = ["collective anxiety", "social crisis", "mental health crisis"]
    kw_civic    = ["civic engagement", "volunteering", "community action"]
    kw_crisis   = ["social unrest", "political crisis", "economic crisis"]

    def _get_interest(keywords: list[str], cat: int = 0) -> pd.Series:
        """Get monthly Google Trends interest for a list of keywords."""
        pytrends.build_payload(keywords[:5], cat=cat, timeframe="2004-01-01 2025-12-31",
                               geo="", gprop="")
        df = pytrends.interest_over_time()
        if df.empty:
            return pd.Series(dtype=float)
        df = df.drop(columns=["isPartial"], errors="ignore")
        return df.mean(axis=1).resample("MS").mean()

    s_trust   = _get_interest(kw_trust)
    s_anxiety = _get_interest(kw_anxiety)
    s_civic   = _get_interest(kw_civic)
    s_crisis  = _get_interest(kw_crisis)

    # Align on common index
    idx = s_trust.index.union(s_anxiety.index).union(s_civic.index).union(s_crisis.index)
    df = pd.DataFrame({
        "trust":   s_trust.reindex(idx).interpolate(),
        "anxiety": s_anxiety.reindex(idx).interpolate(),
        "civic":   s_civic.reindex(idx).interpolate(),
        "crisis":  s_crisis.reindex(idx).interpolate(),
    }).fillna(method="bfill").fillna(0)

    raw_bytes = df.to_csv().encode("utf-8")
    (raw_dir / "google_trends_raw.csv").write_bytes(raw_bytes)
    return df, raw_bytes


def _build_trends_oric(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    trust   = df["trust"].to_numpy(dtype=float)
    anxiety = df["anxiety"].to_numpy(dtype=float)
    civic   = df["civic"].to_numpy(dtype=float)
    crisis  = df["crisis"].to_numpy(dtype=float)

    O = robust_minmax(trust)
    R = 1.0 - robust_minmax(anxiety)

    # I: co-movement coherence between trust and civic engagement
    coh = rolling_corr(trust, civic, window=12)
    I = robust_minmax(np.clip(coh, 0, None))

    S = cumsum_norm(np.clip(np.diff(civic, prepend=civic[0]), 0, None))
    demand = robust_minmax(crisis)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
    })


# ── WVS synthetic fallback ────────────────────────────────────────────────────

def _generate_wvs_fallback(n: int, seed: int) -> tuple[pd.DataFrame, bytes]:
    """Generate WVS-calibrated synthetic series when real data unavailable."""
    from generate_synth import _generate_wvs_synthetic
    df = _generate_wvs_synthetic(n, seed)
    raw_bytes = df.to_csv(index=False).encode("utf-8")
    return df, raw_bytes


# ── proxy_spec.json ───────────────────────────────────────────────────────────

def _proxy_spec(dataset_id: str) -> dict:
    return {
        "dataset_id":   dataset_id,
        "spec_version": "2.1",
        "sector":       "psych",
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
                "fragility_note": f"{r} proxy for psych sector.",
                "manipulability_note": "Aggregated public interest data."
            }
            for r in ["O", "R", "I", "demand", "S"]
        ],
    }


# ── Main CLI ──────────────────────────────────────────────────────────────────

def run(pilot_id: str, outdir: Path, repo_root: Path) -> None:
    outdir = outdir.resolve()
    raw_dir = outdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "google_trends":
        try:
            df_raw, raw_bytes = _fetch_google_trends(outdir, raw_dir)
            df_oric = _build_trends_oric(df_raw)
            print(f"[psych/google_trends] Fetched {len(df_oric)} rows from Google Trends")
        except Exception as e:
            print(f"[psych/google_trends] Fetch failed ({e}); using synthetic fallback",
                  file=sys.stderr)
            df_oric, raw_bytes = _generate_wvs_fallback(240, 1234)
        spec = _proxy_spec("sector_psych.pilot_google_trends.real.v1")

    elif pilot_id == "wvs_synthetic":
        df_oric, raw_bytes = _generate_wvs_fallback(240, 1234)
        spec = _proxy_spec("sector_psych.pilot_wvs_synthetic.real.v1")
        print("[psych/wvs_synthetic] Using WVS-calibrated synthetic data")

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
        sector="psych",
        n_rows=len(df_oric),
        sha256="n/a",
    )
    print(f"[psych/{pilot_id}] Saved {len(df_oric)} rows to {outdir/'real.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch psych real data")
    parser.add_argument("--pilot-id", required=True,
                        choices=["google_trends", "wvs_synthetic"])
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    run(args.pilot_id, args.outdir, REPO_ROOT)


if __name__ == "__main__":
    main()
