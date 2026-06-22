#!/usr/bin/env python3
"""build_data_pack_manifest.py — (re)generate data_pack_manifest.json.

The manifest is the integrity record of the **frozen data pack**: the source
bundle zips plus the small committed reference datasets. It deliberately does
NOT list ``data/bundles_extracted/`` — those are *regenerable* artefacts derived
from the zips (``python -m tools.extract_bundles``); hashing the zips already
pins their content. See docs/ARTIFACTS_POLICY.md.

Scope = every git-tracked file under the frozen-reference directories below.
Using ``git ls-files`` (not a raw walk) guarantees we never hash a stray,
untracked or generated file.

Usage:
    python -m tools.build_data_pack_manifest          # write data_pack_manifest.json
    python -m tools.build_data_pack_manifest --check  # fail if it would change (CI)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_pack_manifest.json"

# Frozen-reference directories (the data pack). Order is irrelevant; output is sorted.
FROZEN_DIRS = [
    "data/bundles",     # the source bundle zips (canonical, hashed here)
    "data/climate",     # small reference series
    "data/finance",     # small reference series
    "data/qcc",         # QCC reference data
    "data/survey",      # survey reference data
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *FROZEN_DIRS],
        cwd=str(ROOT), capture_output=True, text=True, check=True,
    )
    return sorted(line for line in out.stdout.splitlines() if line)


def build(*, generated_utc: str | None = None) -> dict:
    entries = []
    for rel in _tracked_files():
        p = ROOT / rel
        if not p.is_file():
            continue
        entries.append({"path": rel, "sha256": _sha256(p), "bytes": p.stat().st_size})
    return {
        "schema": "oric.data_pack_manifest.v2",
        "description": (
            "Integrity record of the FROZEN data pack: source bundle zips + small "
            "committed reference datasets. Regenerable artefacts (data/bundles_extracted/) "
            "are intentionally excluded — they derive from the zips. See docs/ARTIFACTS_POLICY.md."
        ),
        "frozen_dirs": FROZEN_DIRS,
        "generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(),
        "n_entries": len(entries),
        "entries": entries,
    }


def _normalized(d: dict) -> dict:
    """Drop the volatile timestamp so --check compares only content."""
    return {k: v for k, v in d.items() if k != "generated_utc"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/refresh data_pack_manifest.json")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the manifest content is out of date (CI)")
    args = ap.parse_args()

    fresh = build()

    if args.check:
        if not MANIFEST.exists():
            print("ERROR: data_pack_manifest.json missing — run the builder.", file=sys.stderr)
            return 1
        current = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if _normalized(current) != _normalized(fresh):
            print(
                "ERROR: data_pack_manifest.json is out of date. "
                "Run `python -m tools.build_data_pack_manifest` and commit.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: data_pack_manifest.json up to date ({fresh['n_entries']} entries).")
        return 0

    # Preserve the previous timestamp if content is unchanged (stable diffs).
    if MANIFEST.exists():
        prev = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if _normalized(prev) == _normalized(fresh):
            fresh["generated_utc"] = prev.get("generated_utc", fresh["generated_utc"])
    MANIFEST.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.name}: {fresh['n_entries']} entries over {len(FROZEN_DIRS)} frozen dirs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
