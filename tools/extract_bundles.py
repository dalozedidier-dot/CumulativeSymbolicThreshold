#!/usr/bin/env python3
"""extract_bundles.py - regenerate data/bundles_extracted/ from data/bundles/*.zip.

``data/bundles_extracted/`` is a regenerable artefact. Every file in it is a
member of one of the committed source zips in ``data/bundles/`` and the zips are
hashed in ``data_pack_manifest.json``. This script reproduces the extracted tree
when a smoke or sector run needs those files.

Usage:
    python -m tools.extract_bundles
    python -m tools.extract_bundles --verify
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "bundles"
DST = ROOT / "data" / "bundles_extracted"


def _safe_extract(zf: zipfile.ZipFile, dst: Path) -> int:
    """Extract a zip while rejecting absolute paths and path traversal."""
    count = 0
    dst_resolved = dst.resolve()
    for member in zf.infolist():
        name = member.filename
        if not name or name.endswith("/"):
            continue
        target = dst / name
        resolved = target.resolve()
        if not str(resolved).startswith(str(dst_resolved) + str(Path.sep)):
            raise ValueError(f"unsafe zip member path: {name!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, target.open("wb") as out:
            shutil.copyfileobj(src, out)
        count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract data/bundles/*.zip into data/bundles_extracted/")
    ap.add_argument("--verify", action="store_true", help="report members only, write nothing")
    ap.add_argument("--clean", action="store_true", help="remove the destination before extraction")
    args = ap.parse_args()

    zips = sorted(SRC.glob("*.zip"))
    if not zips:
        print(f"ERROR: no zips under {SRC.relative_to(ROOT)}", file=sys.stderr)
        return 1

    if args.clean and DST.exists() and not args.verify:
        shutil.rmtree(DST)

    total = 0
    try:
        for z in zips:
            with zipfile.ZipFile(z) as zf:
                members = [m for m in zf.namelist() if m and not m.endswith("/")]
                if args.verify:
                    for name in members:
                        target = (DST / name).resolve()
                        dst_resolved = DST.resolve()
                        if not str(target).startswith(str(dst_resolved) + str(Path.sep)):
                            raise ValueError(f"unsafe zip member path: {name!r}")
                    total += len(members)
                    print(f"  {z.name}: {len(members)} file(s)")
                    continue
                n = _safe_extract(zf, DST)
                total += n
                print(f"  extracted {n} file(s) from {z.name}")
    except (zipfile.BadZipFile, ValueError) as exc:
        print(f"ERROR: bundle extraction failed: {exc}", file=sys.stderr)
        return 1

    action = "would extract" if args.verify else "extracted"
    print(f"\n{action} {total} file(s) from {len(zips)} bundle(s) -> {DST.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
