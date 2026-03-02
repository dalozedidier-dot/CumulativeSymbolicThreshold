"""
qcc_stateprob_write_manifest.py

Purpose
- Ensure each QCC StateProb run directory contains a manifest.json with sha256 hashes.
- Designed for CI: run after tools.qcc_stateprob_cross_conditions and before checks.

Usage
  python -m tools.qcc_stateprob_write_manifest --out-root _ci_out/qcc_stateprob_cross

Notes
- This script is purely mechanical: it hashes files that already exist.
- It does not compute any scientific metric, threshold, or verdict.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _list_files(run_dir: Path) -> List[Path]:
    # Hash all regular files under run_dir, excluding obvious noise.
    excluded_dirs = {"__pycache__", ".pytest_cache", ".git"}
    excluded_files = {".DS_Store"}

    files: List[Path] = []
    for p in run_dir.rglob("*"):
        if p.is_dir():
            # Skip excluded dirs early (best-effort).
            if p.name in excluded_dirs:
                continue
            continue
        if p.name in excluded_files:
            continue
        # Skip symlinks (rare in CI, but be safe).
        if p.is_symlink():
            continue
        files.append(p)
    return sorted(files, key=lambda x: x.as_posix())


def _select_latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"Missing runs/ directory under out-root: {runs_dir}")

    candidates = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No run directories found under: {runs_dir}")

    # Prefer lexicographic order (timestamps YYYYMMDD_HHMMSS), fallback to mtime.
    candidates_sorted = sorted(candidates, key=lambda p: p.name)
    latest = candidates_sorted[-1]
    return latest


def write_manifest(run_dir: Path) -> Path:
    files = _list_files(run_dir)
    entries: List[Dict[str, object]] = []
    for f in files:
        rel = f.relative_to(run_dir).as_posix()
        entries.append(
            {
                "path": rel,
                "sha256": _sha256_file(f),
                "bytes": f.stat().st_size,
            }
        )

    manifest = {
        "schema": "qcc.manifest.v1",
        "created_utc": _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc).isoformat(),
        "run_dir": run_dir.as_posix(),
        "file_count": len(entries),
        "files": entries,
    }

    out_path = run_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Output root containing runs/<timestamp>/")
    ap.add_argument(
        "--run-dir",
        default="",
        help="Optional explicit run directory. If omitted, selects latest under out-root/runs/.",
    )
    args = ap.parse_args()

    out_root = Path(args.out_root)
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = _select_latest_run_dir(out_root)

    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    manifest_path = write_manifest(run_dir)
    print(f"Wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
