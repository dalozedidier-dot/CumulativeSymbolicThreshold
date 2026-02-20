#!/usr/bin/env python3
"""Resolve dataset list for a real-data run.

Priority:
1) If --dataset is provided, return that single path.
2) Else, return pilot datasets under 03_Data/real/<sector>/pilot_*/real.csv
3) Optionally include bundle processed CSVs under 03_Data/real/_bundles/**/data_real_v*/processed/*.csv

Outputs JSON list of repo-relative paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector", required=True)
    ap.add_argument("--dataset", default="")
    ap.add_argument("--include-bundles", action="store_true")
    args = ap.parse_args()

    if args.dataset:
        print(json.dumps([args.dataset], indent=2))
        return 0

    base = Path("03_Data") / "real" / args.sector
    out: list[str] = []

    if base.exists():
        for p in sorted(base.rglob("real.csv")):
            if "_bundles" in p.parts:
                continue
            if "pilot_" in "/".join(p.parts):
                out.append(p.as_posix())

    if args.include_bundles:
        bundles = Path("03_Data") / "real" / "_bundles"
        if bundles.exists():
            for p in sorted(bundles.glob("**/data_real_v*/processed/*.csv")):
                if p.is_file():
                    out.append(p.as_posix())

    # de-dup
    seen = set()
    dedup = []
    for p in out:
        if p not in seen:
            seen.add(p)
            dedup.append(p)

    print(json.dumps(dedup, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
