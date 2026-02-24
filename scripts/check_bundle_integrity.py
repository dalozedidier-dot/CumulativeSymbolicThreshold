#!/usr/bin/env python3
"""scripts/check_bundle_integrity.py

Verify SHA-256 hashes of pinned bundle files against bundle_hashes.json.

Exit codes:
  0 — all hashes match
  1 — one or more hashes mismatch (tampering / accidental modification)
  2 — bundle_hashes.json not found or malformed

Usage
-----
    python scripts/check_bundle_integrity.py \\
        --bundle-root 03_Data/real/_bundles \\
        --hashes-file 03_Data/real/_bundles/bundle_hashes.json

    # Strict mode: fail immediately on first mismatch
    python scripts/check_bundle_integrity.py --strict

    # Check a specific bundle version only
    python scripts/check_bundle_integrity.py --filter data_real_v2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify ORI-C bundle file integrity")
    ap.add_argument(
        "--bundle-root",
        default="03_Data/real/_bundles",
        help="Root directory of the bundles (relative to repo root or absolute)",
    )
    ap.add_argument(
        "--hashes-file",
        default="03_Data/real/_bundles/bundle_hashes.json",
        help="Path to bundle_hashes.json",
    )
    ap.add_argument("--strict", action="store_true", help="Abort on first mismatch")
    ap.add_argument("--filter", default=None, help="Only check files containing this substring")
    args = ap.parse_args()

    hashes_path = Path(args.hashes_file)
    if not hashes_path.exists():
        print(f"ERROR: hashes file not found: {hashes_path}", file=sys.stderr)
        return 2

    try:
        spec = json.loads(hashes_path.read_text(encoding="utf-8"))
        files: dict = spec["files"]
    except Exception as exc:
        print(f"ERROR: cannot parse {hashes_path}: {exc}", file=sys.stderr)
        return 2

    bundle_root = Path(args.bundle_root)
    n_ok = 0
    n_fail = 0
    n_skip = 0

    for rel_path, entry in files.items():
        if args.filter and args.filter not in rel_path:
            n_skip += 1
            continue

        full = bundle_root / rel_path
        if not full.exists():
            print(f"MISSING  {rel_path}")
            n_fail += 1
            if args.strict:
                return 1
            continue

        expected = entry["sha256"]
        actual = _sha256_file(full)

        if actual == expected:
            print(f"OK       {rel_path}  {actual[:16]}...")
            n_ok += 1
        else:
            print(f"TAMPERED {rel_path}")
            print(f"         expected: {expected}")
            print(f"         actual:   {actual}")
            n_fail += 1
            if args.strict:
                return 1

    print(f"\nResult: {n_ok} OK, {n_fail} FAILED, {n_skip} skipped")
    if n_fail > 0:
        print("INTEGRITY CHECK FAILED — do not proceed with analysis", file=sys.stderr)
        return 1

    print("INTEGRITY CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
