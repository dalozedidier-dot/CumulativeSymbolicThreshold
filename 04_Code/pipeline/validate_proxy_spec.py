#!/usr/bin/env python3
"""04_Code/pipeline/validate_proxy_spec.py

Thin pipeline adapter for the canonical validator (scripts/validate_proxy_spec.py).

Interface used by CI pipeline workflows:
    python 04_Code/pipeline/validate_proxy_spec.py --spec <proxy_spec.json>
    python 04_Code/pipeline/validate_proxy_spec.py --spec <proxy_spec.json> --csv <data.csv>

Structural validation is fully delegated to the canonical implementation.
The optional --csv flag checks that every source_column name exists in the CSV header row.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Make repo root importable so the `scripts` package is reachable regardless of cwd
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.validate_proxy_spec import validate_file  # noqa: E402


def _check_csv_headers(spec: dict, csv_path: Path) -> list[str]:
    """Return error strings for source_columns absent from the CSV header row."""
    errors: list[str] = []
    try:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            try:
                headers = [h.strip() for h in next(reader)]
            except StopIteration:
                return [f"CSV file is empty: {csv_path}"]
    except Exception as exc:  # noqa: BLE001
        return [f"could not read CSV header from {csv_path}: {exc}"]

    for i, col in enumerate(spec.get("columns", [])):
        src = col.get("source_column", "")
        if src and src not in headers:
            ov = col.get("oric_variable", "?")
            errors.append(
                f"columns[{i}]: source_column '{src}' (-> {ov}) not found in CSV headers"
            )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Validate a proxy_spec.json before an ORI-C real data run. "
            "Delegates to scripts/validate_proxy_spec.py (canonical). "
            "Exits 0 on success, 1 on any validation error."
        )
    )
    ap.add_argument("--spec", required=True, help="Path to proxy_spec.json")
    ap.add_argument(
        "--csv",
        default=None,
        help="Optional path to CSV data file — verifies source_column headers exist",
    )
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    ok = validate_file(spec_path, verbose=args.verbose)

    if ok and args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(
                f"[validate_proxy_spec] FAIL — --csv file not found: {csv_path}",
                file=sys.stderr,
            )
            return 1
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        errs = _check_csv_headers(spec, csv_path)
        if errs:
            print(
                f"[validate_proxy_spec] FAIL — {len(errs)} CSV header error(s):",
                file=sys.stderr,
            )
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
            return 1

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
