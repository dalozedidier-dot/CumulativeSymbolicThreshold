from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        st = p.stat()
        entries.append(
            {
                "path": rel,
                "sha256": sha256_file(p),
                "bytes": st.st_size,
            }
        )
    return {
        "root": root.as_posix(),
        "n_files": len(entries),
        "files": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Root directory to hash.")
    ap.add_argument("--out", required=True, help="Output JSON path.")
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(root)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
