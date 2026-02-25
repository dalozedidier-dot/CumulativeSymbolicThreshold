"""fetch_all_real_data.py — Master script: download all real sector data.

Runs all three sector fetchers in sequence and reports a summary.
No synthetic fallback — if any download fails, the error is printed clearly.

Usage:
  python 04_Code/sector/fetch_all_real_data.py

  # Single sector:
  python 04_Code/sector/fetch_all_real_data.py --sectors bio
  python 04_Code/sector/fetch_all_real_data.py --sectors cosmo infra

  # Custom output root:
  python 04_Code/sector/fetch_all_real_data.py --data-root /data/oric

Output:
  03_Data/sector_bio/real/pilot_epidemic/real.csv   + proxy_spec.json + fetch_manifest.json
  03_Data/sector_bio/real/pilot_ecology/real.csv    + ...
  03_Data/sector_cosmo/real/pilot_solar/real.csv    + ...
  03_Data/sector_infra/real/pilot_finance/real.csv  + ...

Each pilot also writes:
  raw/          — original downloaded file(s) with sha256 in manifest
  fetch_manifest.json — url, sha256, n_rows, date_range, license
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE / "bio"))
sys.path.insert(0, str(_HERE / "cosmo"))
sys.path.insert(0, str(_HERE / "infra"))
sys.path.insert(0, str(_HERE / "shared"))

from fetch_utils import save_real_csv


def _run_bio(data_root: Path, country: str) -> list[tuple[str, str, str]]:
    from fetch_real_data import fetch_epidemic, fetch_ecology, _write_proxy_spec   # bio module

    results = []
    for pilot, fn in [("epidemic", lambda o: fetch_epidemic(o, country=country)),
                      ("ecology",  lambda o: fetch_ecology(o))]:
        out = data_root / "sector_bio" / "real" / f"pilot_{pilot}"
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        try:
            df = fn(out)
            save_real_csv(df, out / "real.csv")
            _write_proxy_spec(out, pilot)
            elapsed = time.monotonic() - t0
            results.append(("bio", pilot, f"OK  {len(df):4d} rows  {elapsed:.1f}s"))
        except Exception as exc:
            results.append(("bio", pilot, f"FAILED: {exc}"))
    return results


def _run_cosmo(data_root: Path, start_year: int) -> list[tuple[str, str, str]]:
    from fetch_real_data import fetch_solar, _write_proxy_spec  # cosmo module

    results = []
    out = data_root / "sector_cosmo" / "real" / "pilot_solar"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    try:
        df = fetch_solar(out, start_year=start_year)
        save_real_csv(df, out / "real.csv")
        _write_proxy_spec(out)
        elapsed = time.monotonic() - t0
        results.append(("cosmo", "solar", f"OK  {len(df):4d} rows  {elapsed:.1f}s"))
    except Exception as exc:
        results.append(("cosmo", "solar", f"FAILED: {exc}"))
    return results


def _run_infra(data_root: Path, start: str) -> list[tuple[str, str, str]]:
    from fetch_real_data import fetch_finance, _write_proxy_spec  # infra module

    results = []
    out = data_root / "sector_infra" / "real" / "pilot_finance"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    try:
        df = fetch_finance(out, start=start)
        save_real_csv(df, out / "real.csv")
        _write_proxy_spec(out)
        elapsed = time.monotonic() - t0
        results.append(("infra", "finance", f"OK  {len(df):4d} rows  {elapsed:.1f}s"))
    except Exception as exc:
        results.append(("infra", "finance", f"FAILED: {exc}"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download all ORI-C sector real data from public sources"
    )
    parser.add_argument(
        "--sectors", nargs="+",
        choices=["bio", "cosmo", "infra"],
        default=["bio", "cosmo", "infra"],
    )
    parser.add_argument("--data-root", default=None,
                        help="Base data directory (default: 03_Data/)")
    parser.add_argument("--country",    default="FRA",
                        help="ISO code for epidemic pilot (default: FRA)")
    parser.add_argument("--start-year", type=int, default=1960,
                        help="Start year for solar data (default: 1960)")
    parser.add_argument("--start-date", default="2004-01-01",
                        help="Start date for finance data (default: 2004-01-01)")
    args = parser.parse_args()

    data_root = Path(args.data_root) if args.data_root else (_REPO_ROOT / "03_Data")

    print(f"\n{'='*65}")
    print("  ORI-C SECTOR PANEL — REAL DATA FETCH")
    print(f"  data_root: {data_root}")
    print(f"  sectors:   {args.sectors}")
    print(f"{'='*65}\n")

    all_results: list[tuple[str, str, str]] = []

    if "bio" in args.sectors:
        all_results.extend(_run_bio(data_root, args.country))

    if "cosmo" in args.sectors:
        all_results.extend(_run_cosmo(data_root, args.start_year))

    if "infra" in args.sectors:
        all_results.extend(_run_infra(data_root, args.start_date))

    # Summary
    print(f"\n{'='*65}")
    print("  FETCH SUMMARY")
    print(f"{'='*65}")
    n_ok = n_fail = 0
    for sector, pilot, status in all_results:
        ok = status.startswith("OK")
        marker = "✓" if ok else "✗"
        print(f"  {marker} {sector:6s} / {pilot:12s}  {status}")
        if ok: n_ok += 1
        else:  n_fail += 1

    print(f"\n  {n_ok}/{n_ok+n_fail} pilots fetched successfully.")
    if n_fail:
        print("  FAILED pilots — check network connectivity and retry.")
        return 1

    print(f"\n  To run sector suites with real data:")
    print(f"    python 04_Code/sector/bio/run_sector_suite.py \\")
    print(f"        --pilot-id epidemic \\")
    print(f"        --real-csv 03_Data/sector_bio/real/pilot_epidemic/real.csv \\")
    print(f"        --outdir 05_Results/sector_bio/real_001 --seed 1234")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
