#!/usr/bin/env python3
"""verify_data_pack.py — verify the frozen data pack against data_pack_manifest.json.

Checks, for every manifest entry:
  - the file exists,
  - its byte size matches,
  - its sha256 matches.
And, for completeness, that every git-tracked file under the manifest's
``frozen_dirs`` is listed (so a newly added reference file cannot silently escape
the integrity record).

Exit codes: 0 = all good · 1 = mismatch / missing / unlisted · 2 = manifest bad.

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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
                f"(manifest={str(it.get('sha256'))[:16]}… actual={digest[:16]}…)"
            )

    # Completeness: every tracked file under frozen_dirs must be listed.
    frozen_dirs = manifest.get("frozen_dirs", [])
    if frozen_dirs:
        out = subprocess.run(
            ["git", "ls-files", *frozen_dirs],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        for rel in out.stdout.splitlines():
            if rel and rel not in listed:
                errors.append(f"UNLISTED tracked frozen file (run the builder): {rel}")

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
