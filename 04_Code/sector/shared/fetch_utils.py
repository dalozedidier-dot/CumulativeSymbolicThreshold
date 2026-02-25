"""fetch_utils.py — Shared download utilities for real-data sector fetchers.

Principles:
  - All downloads from public, auth-free URLs
  - Retry with exponential backoff (4 tries: 2s, 4s, 8s, 16s)
  - SHA-256 computed immediately after download
  - Every fetch writes a fetch_manifest.json alongside real.csv
  - Normalisation helpers: robust_minmax (default) and minmax
  - No synthetic fallback — if download fails, fail loudly
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ── Download ─────────────────────────────────────────────────────────────────

_USER_AGENT = (
    "Mozilla/5.0 (compatible; ORI-C-fetcher/1.0; "
    "+https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold)"
)


def download_bytes(url: str, retries: int = 4, timeout: int = 120) -> bytes:
    """Download URL → bytes.  Retry up to `retries` times with exp backoff."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            print(f"  [fetch] {url}  ({len(data)/1024:.0f} kB)")
            return data
        except (urllib.error.URLError, OSError) as exc:
            last_exc = exc
            wait = 2 ** (attempt + 1)
            print(f"  [fetch] attempt {attempt+1}/{retries} failed: {exc}  (retry in {wait}s)")
            time.sleep(wait)
    raise RuntimeError(
        f"Download failed after {retries} attempts: {url}"
    ) from last_exc


def download_file(url: str, dest: Path, retries: int = 4, timeout: int = 120) -> None:
    """Download URL → file at dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = download_bytes(url, retries=retries, timeout=timeout)
    dest.write_bytes(data)


# ── SHA-256 ───────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Manifest ──────────────────────────────────────────────────────────────────

def write_manifest(
    manifest_path: Path,
    *,
    sector: str,
    pilot: str,
    sources: list[dict[str, Any]],
    n_rows: int,
    date_range: tuple[str, str] | None = None,
    notes: str = "",
) -> None:
    """Write fetch_manifest.json."""
    manifest = {
        "sector":      sector,
        "pilot":       pilot,
        "fetched_at":  datetime.now(timezone.utc).isoformat(),
        "n_rows":      n_rows,
        "date_range":  {"start": date_range[0], "end": date_range[1]} if date_range else None,
        "sources":     sources,
        "notes":       notes,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  [manifest] → {manifest_path}")


# ── Normalisation ─────────────────────────────────────────────────────────────

def robust_minmax(series: pd.Series, q_lo: float = 0.02, q_hi: float = 0.98) -> pd.Series:
    """Clip to [q_lo, q_hi] quantiles then scale to [0, 1]."""
    lo = series.quantile(q_lo)
    hi = series.quantile(q_hi)
    if hi <= lo:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return ((series.clip(lo, hi) - lo) / (hi - lo)).clip(0, 1)


def minmax(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi <= lo:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return ((series - lo) / (hi - lo)).clip(0, 1)


def cumsum_norm(series: pd.Series, decay: float = 0.005) -> pd.Series:
    """Cumulative sum with exponential decay → normalised [0,1].
    Simulates a symbolic stock with memory (S channel)."""
    arr = series.fillna(0).to_numpy(float)
    out = np.zeros(len(arr))
    for t in range(1, len(arr)):
        out[t] = out[t-1] * (1 - decay) + arr[t]
    return robust_minmax(pd.Series(out, index=series.index))


def rolling_corr(a: pd.Series, b: pd.Series, window: int = 24) -> pd.Series:
    """Rolling Pearson correlation between two series → [0,1] (absolute value)."""
    corr = a.rolling(window, min_periods=window // 2).corr(b).abs()
    return corr.fillna(method="bfill").fillna(0).clip(0, 1)


# ── Save ──────────────────────────────────────────────────────────────────────

def save_real_csv(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"  [save] {out_path}  ({len(df)} rows × {len(df.columns)} cols)")
