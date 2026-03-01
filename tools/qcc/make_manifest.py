\
#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(root: Path) -> Dict[str, Any]:
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            files.append({
                "path": rel,
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            })
    return {
        "root": root.as_posix(),
        "files": files,
    }


def write_manifest(root: Path, out_path: Path) -> None:
    man = build_manifest(root)
    out_path.write_text(json.dumps(man, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, required=True)
    ap.add_argument("--out", type=str, required=True)
    args = ap.parse_args()
    write_manifest(Path(args.root), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
