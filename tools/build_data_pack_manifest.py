#!/usr/bin/env python3
"""build_data_pack_manifest.py - regenerate data_pack_manifest.json.

The manifest is the integrity record of the frozen data pack: the source bundle
zips plus the small committed reference datasets. It deliberately does NOT list
``data/bundles_extracted/``. Those files are regenerable artefacts derived from
``data/bundles/*.zip`` by ``python -m tools.extract_bundles``.

In a normal checkout, the builder uses ``git ls-files`` so only tracked data is
hashed. In a source archive without ``.git/``, it falls back to a conservative
filesystem walk over the same frozen-reference directories. This keeps
``--check`` usable for Zenodo/source-archive replication.

Usage:
    python -m tools.build_data_pack_manifest
    python -m tools.build_data_pack_manifest --check
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

FROZEN_DIRS = [
    "data/bundles",
    "data/climate",
    "data/finance",
    "data/qcc",
    "data/survey",
]

EXCLUDED_DIRS = {
    "data/bundles_extracted",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_excluded(rel: Path) -> bool:
    rel_posix = rel.as_posix()
    if any(rel_posix == d or rel_posix.startswith(d + "/") for d in EXCLUDED_DIRS):
        return True
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    return rel.suffix in EXCLUDED_SUFFIXES


def _git_tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *FROZEN_DIRS],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(line for line in out.stdout.splitlines() if line)


def _filesystem_files() -> list[str]:
    files: list[str] = []
    for dirname in FROZEN_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT)
            if _is_excluded(rel):
                continue
            files.append(rel.as_posix())
    return sorted(files)


def _tracked_files() -> list[str]:
    try:
        return _git_tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _filesystem_files()


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
            "are intentionally excluded because they derive from the zips. See docs/ARTIFACTS_POLICY.md."
        ),
        "frozen_dirs": FROZEN_DIRS,
        "generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(),
        "n_entries": len(entries),
        "entries": entries,
    }


def _normalized(d: dict) -> dict:
    """Drop volatile fields so --check compares only content."""
    return {k: v for k, v in d.items() if k != "generated_utc"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/refresh data_pack_manifest.json")
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the manifest content is out of date",
    )
    args = ap.parse_args()

    fresh = build()

    if args.check:
        if not MANIFEST.exists():
            print("ERROR: data_pack_manifest.json missing. Run the builder.", file=sys.stderr)
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

    if MANIFEST.exists():
        prev = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if _normalized(prev) == _normalized(fresh):
            fresh["generated_utc"] = prev.get("generated_utc", fresh["generated_utc"])
    MANIFEST.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.name}: {fresh['n_entries']} entries over {len(FROZEN_DIRS)} frozen dirs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
