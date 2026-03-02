#!/usr/bin/env python3
"""Non-interpretive checks for QCC StateProb Cross-Conditions outputs.

This checker is intentionally mechanical:
- find latest run directory under <out_root>/runs/
- verify required files exist inside the run
- verify manifest.json exists and hashes required outputs (but does NOT require self-hashing)

Exit code 1 on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_RELATIVE = [
    "tables/summary.json",
    "tables/inventory.csv",
    "tables/recommendations.json",
    "tables/selected_plan.json",
    "tables/ccl_points.csv",
    "tables/ccl_by_shots.csv",
    "tables/tstar_by_shots.csv",
    "tables/bootstrap_tstar_by_shots.csv",
    "figures/ccl_vs_axis_by_shots.png",
    "figures/tstar_hist.png",
    "contracts/mapping_cross_conditions.json",
    "params.txt",
    "manifest.json",
]


def _latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists() or not runs_dir.is_dir():
        raise FileNotFoundError(f"No runs directory: {runs_dir}")
    run_dirs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    if not run_dirs:
        raise FileNotFoundError(f"No run directories inside: {runs_dir}")
    return run_dirs[-1]


def _load_manifest(manifest_path: Path) -> dict:
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Root output dir (contains runs/)")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    try:
        run_dir = _latest_run_dir(out_root)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    missing = []
    for rel in REQUIRED_RELATIVE:
        p = run_dir / rel
        if not p.exists():
            missing.append(rel)

    if missing:
        print(f"Missing required outputs in {run_dir}: {missing}", file=sys.stderr)
        return 1

    # Manifest coverage checks
    manifest_path = run_dir / "manifest.json"
    try:
        manifest = _load_manifest(manifest_path)
    except Exception as e:
        print(f"Failed to read manifest.json: {e}", file=sys.stderr)
        return 1

    entries = manifest.get("entries")
    # Support qcc.manifest.v1 schema written by qcc_stateprob_write_manifest
    # (uses "files" list instead of "entries" dict)
    if entries is None and "files" in manifest:
        files_list = manifest.get("files", [])
        if isinstance(files_list, list):
            entries = {
                item["path"]: item.get("sha256")
                for item in files_list
                if isinstance(item, dict) and "path" in item
            }
    if not isinstance(entries, dict) or not entries:
        print("manifest.json missing or invalid 'entries' dict", file=sys.stderr)
        return 1

    # Ensure required outputs are present in entries (excluding manifest itself)
    required_for_hash = [r for r in REQUIRED_RELATIVE if r != "manifest.json"]
    missing_in_manifest = []
    for rel in required_for_hash:
        # manifest keys are stored as relative paths from run_dir
        if rel not in entries:
            missing_in_manifest.append(rel)

    if missing_in_manifest:
        print(
            f"Manifest missing entries (relative to run_dir) in {run_dir}: {missing_in_manifest}",
            file=sys.stderr,
        )
        return 1

    # Also ensure entries do NOT require self-hash (allowed either way, but never required)
    print(f"Checks OK for run: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
