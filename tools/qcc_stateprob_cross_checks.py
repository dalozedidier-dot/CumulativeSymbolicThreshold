#!/usr/bin/env python3
"""Non-interpretative checks for QCC StateProb Cross-Conditions outputs.

This checker is intentionally mechanical:
- find the latest run under <out_root>/runs/<timestamp>/
- ensure required tables/figures/contracts exist
- ensure manifest.json exists and includes hashes for produced files
No scientific judgement is performed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"runs dir not found: {runs_dir}")
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not run_dirs:
        raise FileNotFoundError(f"no runs found under: {runs_dir}")
    # timestamp dirs sort lexicographically correctly (YYYYmmdd_HHMMSS)
    return sorted(run_dirs, key=lambda p: p.name)[-1]


def _read_manifest(manifest_path: Path) -> dict:
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"failed to read manifest {manifest_path}: {e}") from e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, required=True, help="Output root containing runs/")
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    try:
        run_dir = _latest_run_dir(out_root)
    except Exception as e:
        print(f"Checks failed: {e}", file=sys.stderr)
        return 1

    missing: list[str] = []
    required_rel = [
        "tables/inventory.csv",
        "tables/recommendations.json",
        "tables/ccl_points.csv",
        "tables/ccl_by_shots.csv",
        "tables/tstar_by_shots.csv",
        "tables/bootstrap_tstar_by_shots.csv",
        "tables/summary.json",
        "figures/ccl_vs_axis_by_shots.png",
        "contracts/mapping_cross_conditions.json",
        "manifest.json",
    ]

    for rel in required_rel:
        if not (run_dir / rel).exists():
            missing.append(rel)

    if missing:
        print(f"Missing required outputs in {run_dir.name}: {missing}", file=sys.stderr)
        return 1

    # Validate manifest contains entries for required files (except itself is optional, but we include it too)
    manifest = _read_manifest(run_dir / "manifest.json")
    files = set(manifest.get("files", {}).keys()) if isinstance(manifest.get("files"), dict) else set(manifest.keys())
    # Support two manifest shapes:
    # 1) {"files": {"path": {"sha256": "...", ...}, ...}, ...}
    # 2) {"path": "sha256", ...}
    if "files" in manifest and isinstance(manifest["files"], dict):
        files = set(manifest["files"].keys())
    elif isinstance(manifest, dict):
        files = set(manifest.keys())

    missing_in_manifest = [rel for rel in required_rel if rel != "manifest.json" and rel not in files]
    if missing_in_manifest:
        print(f"Manifest missing entries: {missing_in_manifest}", file=sys.stderr)
        return 1

    print(f"OK: checks passed for latest run {run_dir.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
