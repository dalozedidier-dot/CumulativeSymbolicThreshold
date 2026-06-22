#!/usr/bin/env python3
"""extract_bundles.py — regenerate data/bundles_extracted/ from data/bundles/*.zip.

``data/bundles_extracted/`` is a *regenerable* artefact: every file in it is a
member of one of the committed source zips in ``data/bundles/`` (hashed in
data_pack_manifest.json). This script reproduces it deterministically.

Why it exists: the smoke index (``data/real_datasets_index.csv``) points a few
``smoke_candidate`` datasets at extracted paths, so the extracted tree must be
present to run ``make smoke`` on a fresh checkout. Run this once after cloning.

Usage:
    python -m tools.extract_bundles            # extract into data/bundles_extracted/
    python -m tools.extract_bundles --verify   # list members, do not write
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "bundles"
DST = ROOT / "data" / "bundles_extracted"


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract data/bundles/*.zip into data/bundles_extracted/")
    ap.add_argument("--verify", action="store_true", help="report members only, write nothing")
    args = ap.parse_args()

    zips = sorted(SRC.glob("*.zip"))
    if not zips:
        print(f"ERROR: no zips under {SRC.relative_to(ROOT)}", file=sys.stderr)
        return 1

    total = 0
    for z in zips:
        with zipfile.ZipFile(z) as zf:
            members = [m for m in zf.namelist() if not m.endswith("/")]
            total += len(members)
            if args.verify:
                print(f"  {z.name}: {len(members)} file(s)")
                continue
            zf.extractall(DST)
            print(f"  extracted {len(members)} file(s) from {z.name}")

    action = "would extract" if args.verify else "extracted"
    print(f"\n{action} {total} file(s) from {len(zips)} bundle(s) → {DST.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
