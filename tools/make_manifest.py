#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def build_manifest(root: Path, exclude_names: set[str]) -> dict:
    entries = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        if p.name in exclude_names:
            continue
        entries[rel] = sha256_file(p)
    return {"root": root.as_posix(), "entries": entries}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Directory to hash")
    ap.add_argument("--out", required=True, help="Output manifest JSON file path")
    ap.add_argument("--exclude", default="manifest.json", help="Comma-separated basenames to exclude (default: manifest.json)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    exclude_names = {s.strip() for s in args.exclude.split(",") if s.strip()}
    mani = build_manifest(root, exclude_names=exclude_names)
    out.write_text(json.dumps(mani, indent=2, sort_keys=True), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
