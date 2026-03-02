from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest_sha256(root_dir: Path, out_path: Path) -> None:
    root_dir = root_dir.resolve()
    files: Dict[str, str] = {}

    for p in sorted(root_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root_dir).as_posix()
        if out_path.exists() and rel == out_path.relative_to(root_dir).as_posix():
            continue
        files[rel] = sha256_file(p)

    payload = {"root": root_dir.as_posix(), "files": files}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
