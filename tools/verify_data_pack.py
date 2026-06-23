#!/usr/bin/env python3
"""verify_data_pack.py - verify the frozen data pack against data_pack_manifest.json.

Checks, for every manifest entry:
  - the file exists,
  - its byte size matches,
  - its sha256 matches.

It also checks completeness: every frozen data-pack file visible in the current
checkout/archive must be listed. In a normal Git checkout this uses ``git
ls-files``. In a source archive without ``.git/`` it falls back to the same
conservative filesystem walk used by ``tools.build_data_pack_manifest``. That
keeps OSF/Zenodo archive-mode validation equivalent to Git checkout validation.

Exit codes: 0 = all good, 1 = mismatch / missing / unlisted, 2 = manifest bad.

Usage:
    python -m tools.verify_data_pack
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_pack_manifest.json"

FALLBACK_FROZEN_DIRS = [
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


def _filesystem_files(frozen_dirs: list[str]) -> list[str]:
    files: list[str] = []
    for dirname in frozen_dirs:
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


def _visible_frozen_files(frozen_dirs: list[str]) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", *frozen_dirs],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return sorted(line for line in out.stdout.splitlines() if line)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _filesystem_files(frozen_dirs)


def verify() -> list[str]:
    """Return a list of error strings (empty == clean)."""
    errors: list[str] = []
    if not MANIFEST.exists():
        return ["data_pack_manifest.json not found"]
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"data_pack_manifest.json is not valid JSON: {e}"]

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return ["data_pack_manifest.json has no 'entries' list"]

    listed: set[str] = set()
    for it in entries:
        rel = it.get("path", "")
        listed.add(rel)
        p = ROOT / rel
        if not p.is_file():
            errors.append(f"MISSING file: {rel}")
            continue
        size = p.stat().st_size
        if it.get("bytes") != size:
            errors.append(f"BYTES mismatch: {rel} (manifest={it.get('bytes')} actual={size})")
        digest = _sha256(p)
        if it.get("sha256") != digest:
            errors.append(
                f"SHA256 mismatch: {rel} "
                f"(manifest={str(it.get('sha256'))[:16]}... actual={digest[:16]}...)"
            )

    frozen_dirs = manifest.get("frozen_dirs") or FALLBACK_FROZEN_DIRS
    for rel in _visible_frozen_files(list(frozen_dirs)):
        if rel and rel not in listed:
            errors.append(f"UNLISTED frozen file (run the builder): {rel}")

    return errors


def main() -> int:
    errors = verify()
    if not errors:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        print(f"OK: data pack verified ({manifest.get('n_entries', '?')} entries).")
        return 0
    print(f"FAIL: {len(errors)} data-pack integrity error(s):", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
